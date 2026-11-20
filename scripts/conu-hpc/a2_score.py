#!/usr/bin/env python3
"""Score the completed A2 pilot with the local ConU CrossEncoder; no generation."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
import random
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path

import a2_clean as cleaning
import a2_sample_fixed as sampling

MODEL_REPO = 'cross-encoder/stsb-roberta-large'
MODEL_REVISION = '2b12c2c0088918e76151fd5937b7bba986ef1f98'
WEIGHT_SHA256 = '613af2a4f0a5deb23b07c71649c50a1e1cd76470697f3104e11a7859d80ca832'
MODEL_FILES = ['config.json', 'model.safetensors', 'tokenizer.json', 'tokenizer_config.json',
               'special_tokens_map.json', 'vocab.json', 'merges.txt', 'README.md']


def file_hash(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def jsonl(records):
    return ''.join(json.dumps(row, ensure_ascii=False, sort_keys=True, allow_nan=False) + '\n'
                   for row in records).encode('utf-8')


def reference_blob(repository, revision):
    """Read the authoritative blob from the already pinned local Git commit."""
    return subprocess.run(
        ['git', '-C', str(repository), 'show', f'{revision}:open_domain_qa_similarity.py'],
        check=True, capture_output=True, timeout=15).stdout


def similarity_source_provenance(repository, revision):
    source = (repository / 'open_domain_qa_similarity.py').read_bytes()
    reference = reference_blob(repository, revision)
    source_lf = source.replace(b'\r\n', b'\n')
    reference_lf = reference.replace(b'\r\n', b'\n')
    source_hash = sampling.digest(source_lf)
    reference_hash = sampling.digest(reference_lf)
    if source_lf != reference_lf:
        raise ValueError('Working similarity source differs from its pinned Git blob: '
                         f'actual SHA256 {source_hash}; Git-reference SHA256 {reference_hash}. '
                         'No scoring was started.')
    return {'git_head': revision, 'script': 'third_party/ConU/open_domain_qa_similarity.py',
            'script_lf_sha256': source_hash, 'git_reference_lf_sha256': reference_hash,
            'git_blob_sha1': hashlib.sha1(b'blob ' + str(len(reference)).encode('ascii')
                                        + b'\0' + reference).hexdigest(),
            'verification': 'Compare checkout bytes with git show <pinned-commit>:<file>; normalize CRLF only.'}


def validate_inputs(project):
    """Check the fixed preparation, raw receipts, and exact cleaning before scoring."""
    cache = project / 'cache/a2_conu_pilot_v2'
    questions, _, split, _, preparation_hash = sampling.load_inputs(project)
    plan = sampling.read_json(cache / 'plan.json')
    manifest = sampling.read_json(cache / 'cleaning_manifest.json')
    if (len(questions) != 50 or len(split['calibration_ids']) != 25 or len(split['test_ids']) != 25
            or plan.get('schema') != 'confqa.conu.a2_sampling.v2'
            or plan.get('num_questions') != 50 or plan.get('num_samples') != 5):
        raise ValueError('Expected the frozen 50x5 pilot and its 25/25 split.')
    if file_hash(Path(sampling.__file__)) != plan['script_sha256']:
        raise ValueError('Sampling script changed after generation.')
    if (manifest.get('schema') != 'confqa.conu.a2_cleaning.v1'
            or manifest.get('script_sha256') != file_hash(Path(cleaning.__file__))
            or manifest.get('questions') != 50 or manifest.get('responses') != 250):
        raise ValueError('Cleaning manifest/script does not match the completed pilot.')
    if (preparation_hash != plan['preparation_manifest_sha256']
            or preparation_hash != manifest['prepared_manifest_sha256']
            or file_hash(cache / 'plan.json') != manifest['sampling_plan_sha256']
            or file_hash(project / 'data/splits/triviaqa_a2_pilot.json') != manifest['split_sha256']):
        raise ValueError('Prepared data, sampling plan, or fixed split changed.')
    for name in ['conu_generations.cleaned.jsonl', 'cleaning_report.json']:
        if file_hash(cache / name) != manifest['outputs'][name]['sha256']:
            raise ValueError(f'Cleaning output changed: {name}')
    raw_path = cache / 'conu_generations.jsonl'
    if manifest['input'] != {'file': raw_path.name, 'sha256': file_hash(raw_path)}:
        raise ValueError('Raw generations changed after cleaning.')
    raw = [json.loads(line) for line in raw_path.read_text(encoding='utf-8').splitlines()]
    received, count = sampling.collect(cache, plan)
    if count != 250 or raw != received or [r['qid'] for r in raw] != [q['qid'] for q in questions]:
        raise ValueError('Raw responses differ from the 250 validated generation receipts.')
    upstream = cleaning.upstream_provenance(project)
    records = [json.loads(line) for line in (cache / 'conu_generations.cleaned.jsonl').read_text(encoding='utf-8').splitlines()]
    expected, _ = cleaning.clean_records(raw)
    if records != expected:
        raise ValueError('Cleaned records differ from the exact upstream cleaning of raw responses.')
    for record, question in zip(records, questions):
        if (record['question'] != question['question'] or record['gold'] != question['gold']
                or not isinstance(question.get('gold_value'), str) or not question['gold_value']):
            raise ValueError('Question/gold differs from the frozen prepared data.')
    source_provenance = similarity_source_provenance(project / 'third_party/ConU', upstream['git_head'])
    names = ['cache/a2_conu_pilot_v2/' + name for name in
             ['plan.json', 'conu_generations.jsonl', 'conu_generations.cleaned.jsonl',
              'cleaning_report.json', 'cleaning_manifest.json']]
    names += ['data/processed/triviaqa_a2/manifest.json', 'data/processed/triviaqa_a2/questions.jsonl',
              'data/splits/triviaqa_a2_pilot.json']
    return records, questions, split, {name: file_hash(project / name) for name in names}, source_provenance


def model_provenance(model_dir):
    files = {}
    for name in MODEL_FILES:
        path = model_dir / name
        if path.is_symlink() or not path.is_file():
            raise ValueError(f'Missing local model file: {path}')
        files[name] = {'bytes': path.stat().st_size, 'sha256': file_hash(path)}
    if files['model.safetensors']['sha256'] != WEIGHT_SHA256:
        raise ValueError('Local scorer weights do not match the official pinned SHA256.')
    if sampling.read_json(model_dir / 'config.json').get('model_type') != 'roberta':
        raise ValueError('Expected the RoBERTa CrossEncoder configuration.')
    return {'repository': MODEL_REPO, 'revision': MODEL_REVISION, 'files': files,
            'download_endpoint': 'https://hf-mirror.com', 'weights_verified_against_official_sha256': True}


def finite_score(value):
    number = float(value)
    if not math.isfinite(number) or not 0 <= number <= 1:
        raise ValueError(f'Expected a finite CrossEncoder similarity in [0,1], got {number}')
    return number


def score_record(record, canonical, predict):
    """Exact upstream pair directions, question prefix, diagonal and mirroring."""
    samples = record['samples']
    if len(samples) != 5:
        raise ValueError('Exactly five answer slots are required, including duplicates/errors.')
    texts = [record['question'] + ' ' + answer for answer in samples]
    matrix = [[1.0 if i == j else None for j in range(5)] for i in range(5)]
    for i in range(5):
        for j in range(i + 1, 5):
            matrix[i][j] = matrix[j][i] = finite_score(predict(texts[i], texts[j]))
    gold_text = record['question'] + ' ' + canonical
    correctness = [finite_score(predict(gold_text, answer)) for answer in texts]
    return {'qid': record['qid'], 'question': record['question'], 'role': record['role'],
            'samples': list(samples), 'gold': list(record['gold']), 'canonical_gold': canonical,
            'similarity_matrix': matrix, 'similarity_to_canonical_gold': correctness,
            'predicted_pairs': 15}


def validate_checkpoint(saved, record, canonical, plan_hash):
    if (saved.get('plan_sha256') != plan_hash
            or saved.get('input_record_sha256') != sampling.digest(sampling.encode(record))
            or saved.get('qid') != record['qid'] or saved.get('question') != record['question']
            or saved.get('role') != record['role'] or saved.get('samples') != record['samples']
            or saved.get('gold') != record['gold'] or saved.get('canonical_gold') != canonical
            or saved.get('predicted_pairs') != 15):
        raise ValueError('Saved scoring checkpoint belongs to different data/settings.')
    matrix = saved.get('similarity_matrix', [])
    correctness = saved.get('similarity_to_canonical_gold', [])
    if len(matrix) != 5 or any(len(row) != 5 for row in matrix) or len(correctness) != 5:
        raise ValueError('Invalid score dimensions in checkpoint.')
    for i in range(5):
        finite_score(correctness[i])
        for j in range(5):
            finite_score(matrix[i][j])
            if matrix[i][j] != matrix[j][i] or (i == j and matrix[i][j] != 1.0):
                raise ValueError('Invalid similarity matrix symmetry/diagonal.')
    return saved


def load_predictor(model_dir):
    # All downloads are already complete; scoring uses local files exclusively.
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    import numpy as np
    import torch
    from sentence_transformers import CrossEncoder
    from transformers import AutoTokenizer

    random.seed(10)
    np.random.seed(10)
    torch.manual_seed(10)
    torch.set_num_threads(4)
    if not torch.cuda.is_available():
        raise ValueError('The allocated CUDA device is not available.')
    torch.cuda.reset_peak_memory_stats(0)
    model = CrossEncoder(str(model_dir), num_labels=1, device='cuda:0', local_files_only=True)
    tokenizer = AutoTokenizer.from_pretrained(str(model_dir), local_files_only=True)
    activation = getattr(model, 'activation_fn', None)
    if activation is None:
        activation = getattr(model, 'default_activation_function', None)
    runtime = {'device': str(model.device), 'gpu_name': torch.cuda.get_device_name(0),
               'activation': type(activation).__name__ if activation is not None else 'CrossEncoder default',
               'num_labels': 1, 'backend': 'torch', 'seed': 10,
               'tokenizer_model_max_length': int(tokenizer.model_max_length)}
    max_length = min(512, int(tokenizer.model_max_length))

    def predict(first, second):
        encoded = tokenizer(first, second, add_special_tokens=True, truncation=False)
        if len(encoded['input_ids']) > max_length:
            raise ValueError('A QA pair exceeds the scorer context limit; no silent truncation allowed.')
        # Preserve upstream predict([qa_1, qa_2]); do not apply an extra sigmoid.
        return model.predict([first, second], show_progress_bar=False)

    def resource_stats():
        torch.cuda.synchronize(0)
        return {'peak_cuda_allocated_bytes': torch.cuda.max_memory_allocated(0),
                'peak_cuda_reserved_bytes': torch.cuda.max_memory_reserved(0)}

    return predict, runtime, resource_stats


@contextmanager
def score_lock(root):
    import fcntl
    with (root / 'scoring.lock').open('a+') as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('Another scoring process is already running.')
        yield


def export_scores(root, saved, plan):
    content = jsonl(saved)
    manifest = {'schema': 'confqa.conu.a2_similarity_result.v1',
                'plan_sha256': sampling.digest(sampling.encode(plan)),
                'questions': 50, 'responses': 250, 'predicted_pairs': 750,
                'dropped_questions': 0, 'dropped_responses': 0, 'new_generation_requests': 0,
                'calibration_questions': 25, 'test_questions': 25,
                'outputs': {'scores.jsonl': {'sha256': sampling.digest(content)}},
                'checkpoint_files': {f'questions/{i:04d}.json': file_hash(root / f'questions/{i:04d}.json')
                                     for i in range(50)}}
    products = {'scores.jsonl': content, 'manifest.json': sampling.encode(manifest)}
    for name, data in products.items():
        target = root / name
        if target.is_symlink() or (target.exists() and target.read_bytes() != data):
            raise ValueError(f'Refusing to replace different existing scoring output: {target}')
    for name, data in products.items():
        sampling.atomic_write(root / name, data, immutable=True)


def main(project=None, limit_questions=None, factory=load_predictor):
    project = project or Path(__file__).resolve().parent
    if limit_questions is not None and not 1 <= limit_questions <= 50:
        raise ValueError('Question limit must be between 1 and 50.')
    started = time.monotonic()
    started_at = sampling.timestamp()
    records, questions, split, input_hashes, upstream = validate_inputs(project)
    model_dir = project.parent / 'models/stsb-roberta-large'
    model_info = model_provenance(model_dir)
    plan = {'schema': 'confqa.conu.a2_similarity_plan.v1', 'upstream': upstream,
            'script_sha256': file_hash(Path(__file__)), 'input_sha256': input_hashes,
            'model': model_info, 'questions': [r['qid'] for r in records],
            'canonical_gold': {q['qid']: q['gold_value'] for q in questions},
            'calibration_ids': split['calibration_ids'], 'test_ids': split['test_ids'],
            'packages': {name: importlib.metadata.version(name) for name in
                         ['torch', 'transformers', 'sentence-transformers', 'numpy']},
            'policy': {'question_prefix': 'question + single space + answer',
                       'diagonal': 1.0, 'upper_triangle': 'predict([qa_i, qa_j]) for i < j; mirror lower',
                       'correctness': 'predict([question + canonical gold, question + cleaned sample])',
                       'activation': 'CrossEncoder default with num_labels=1; no additional sigmoid',
                       'duplicates': 'retain and score every original answer slot',
                       'alias_policy': 'canonical gold_value only, as in upstream; no maximum over aliases',
                       'seed': 10, 'device': 'cuda:0', 'silent_truncation': False,
                       'new_generation_requests': 0},
            'adaptations': ['JSONL and per-question checkpoints replace upstream pickle transport.',
                            'Use one allocated CUDA device instead of hard-coded CUDA_VISIBLE_DEVICES=0,1.',
                            'Retain the existing 50x5 question order and fixed calibration/test partition.']}
    root = project / 'cache/a2_conu_pilot_v2/similarity'
    root.mkdir(parents=True, exist_ok=True)
    with score_lock(root):
        sampling.atomic_write(root / 'plan.json', sampling.encode(plan), immutable=True)
        plan_hash = sampling.digest(sampling.encode(plan))
        saved = []
        for i, (record, question) in enumerate(zip(records, questions)):
            path = root / f'questions/{i:04d}.json'
            if path.exists():
                validate_checkpoint(sampling.read_json(path), record, question['gold_value'], plan_hash)
        complete = sum((root / f'questions/{i:04d}.json').exists() for i in range(50))
        print(f'A2 SCORING: {complete}/50 questions already saved; target 250 responses / 750 pairs.', flush=True)
        predictor = None
        runtime = None
        stats = None
        newly_scored = 0
        for i, (record, question) in enumerate(zip(records, questions)):
            if limit_questions is not None and i >= limit_questions:
                break
            path = root / f'questions/{i:04d}.json'
            if path.exists():
                result = validate_checkpoint(sampling.read_json(path), record, question['gold_value'], plan_hash)
            else:
                if predictor is None:
                    predictor, runtime, stats = factory(model_dir)
                    print('Scorer device:', runtime['device'], '; activation:', runtime['activation'], flush=True)
                result = score_record(record, question['gold_value'], predictor)
                result.update({'plan_sha256': plan_hash,
                               'input_record_sha256': sampling.digest(sampling.encode(record))})
                validate_checkpoint(result, record, question['gold_value'], plan_hash)
                sampling.atomic_write(path, sampling.encode(result), immutable=True)
                newly_scored += 1
                print(f'Scored question {i+1}/50 (5 answers, 15 pairs)', flush=True)
            saved.append(result)
        # A concurrent edit cannot silently change the experiment underneath this run.
        if any(file_hash(project / name) != expected for name, expected in input_hashes.items()):
            raise ValueError('An input changed during scoring; final export was not written.')
        if predictor is not None:
            session = {'started_at_utc': started_at, 'finished_at_utc': sampling.timestamp(),
                       'wall_seconds_including_validation': time.monotonic() - started,
                       'newly_scored_questions': newly_scored, 'newly_scored_pairs': newly_scored * 15,
                       'runtime': runtime, 'resource_stats': stats(), 'new_generation_requests': 0}
            sampling.atomic_write(root / 'sessions' / f'{time.time_ns()}.json', sampling.encode(session), immutable=True)
        if len(saved) != 50:
            print(f'A2 SCORING PAUSED AT LIMIT: {len(saved)}/50 questions. Rerun without the limit to continue.', flush=True)
            return
        export_scores(root, saved, plan)
        print('A2 SCORING DONE: 50 questions, 250 answers, 750 pair scores.', flush=True)
        print('Dropped questions: 0; dropped responses: 0', flush=True)
        print('Output:', root / 'scores.jsonl', flush=True)
        print('Calibration/test split retained: 25 / 25. No new answers generated.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit-questions', type=int)
    args = parser.parse_args()
    try:
        main(limit_questions=args.limit_questions)
    except Exception as error:
        raise SystemExit(f'ERROR: {error}') from error
