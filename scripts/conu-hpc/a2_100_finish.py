#!/usr/bin/env python3
"""Finish existing A2 100x20: verify, clean, score, calibrate; no new LLM answers."""
from pathlib import Path
import json

import a2_100_sample as sampling
import a2_clean as cleaning
import a2_score as scoring

io = sampling.pilot


def read_jsonl(path):
    # Unicode NEL/line/paragraph separators are valid inside JSON strings.
    with path.open(encoding='utf-8') as handle:
        return [json.loads(line) for line in handle]


def raw_record(plan, state, qi, plan_hash):
    question = plan['questions'][qi]
    receipts = [state[(qi, si)] for si in range(20)]
    return {**{key: question[key] for key in
               ['qid', 'question', 'gold_value', 'gold', 'role', 'prompt', 'sample_seeds']},
            'samples': [r['response']['choices'][0]['text'] for r in receipts],
            'model': plan['model'], 'decode': plan['decode'],
            'finish_reasons': [r['response']['choices'][0]['finish_reason'] for r in receipts],
            'usage_per_sample': [r['response'].get('usage') for r in receipts],
            'raw_response_files': [f'responses/{qi:04d}-{si:02d}.json' for si in range(20)],
            'reused_sample_indices': [si for si, r in enumerate(receipts)
                                      if r.get('origin', {}).get('kind') == 'reused_pilot'],
            'sampling_plan_sha256': plan_hash}


def validate_raw(project):
    root = project / sampling.CACHE_NAME
    plan = io.read_json(root / 'plan.json')
    plan_hash = scoring.file_hash(root / 'plan.json')
    if (plan.get('schema') != 'confqa.conu.a2_sampling.100x20.v1'
            or plan.get('num_questions') != 100 or plan.get('num_samples') != 20
            or len(plan.get('questions', [])) != 100
            or plan.get('script_sha256') != scoring.file_hash(Path(sampling.__file__))):
        raise ValueError('Expected the unchanged completed A2 100x20 sampling plan/script.')
    dependencies = {Path(module.__file__).name: scoring.file_hash(Path(module.__file__))
                    for module in [sampling.data, sampling.pilot, sampling.scoring, cleaning]}
    if plan.get('dependency_sha256') != dependencies:
        raise ValueError('A sampling dependency changed after generation.')
    prepared, demos, split, old_plan, bindings, upstream = sampling.load_source(project)
    if (plan.get('input_sha256') != bindings or plan.get('upstream') != upstream
            or plan.get('split') != split or io.read_json(root / 'split.json') != split
            or plan.get('old_plan_sha256') != io.digest(io.encode(old_plan))):
        raise ValueError('The frozen source, original pilot, or 50/50 split changed.')
    for key in ['model', 'model_path', 'model_tokenizer_files', 'decode', 'context_limit', 'endpoint']:
        if plan.get(key) != old_plan.get(key):
            raise ValueError(f'Sampling model/settings differ from the original validated pilot: {key}')
    for name, expected in plan['model_tokenizer_files'].items():
        if scoring.file_hash(project.parent / 'models/Qwen2.5-14B-Instruct' / name) != expected:
            raise ValueError(f'Model/tokenizer file changed after generation: {name}')
    calibration = set(split['calibration_ids'])
    for question, source in zip(plan['questions'], prepared):
        if (any(question.get(key) != value for key, value in source.items())
                or question.get('prompt') != io.make_prompt(source, demos)
                or question.get('role') != ('calibration' if source['qid'] in calibration else 'test')
                or len(question.get('sample_seeds', [])) != 20):
            raise ValueError('Sampling question/gold/prompt/role differs from the frozen source.')
    state = sampling.load_saved(project, plan, root, plan_hash)
    if len(state) != 2000:
        raise ValueError(f'Expected all 2000 valid response receipts, found {len(state)}.')
    records = read_jsonl(root / 'conu_generations.jsonl')
    if len(records) != 100 or records != [raw_record(plan, state, qi, plan_hash) for qi in range(100)]:
        raise ValueError('Final raw JSONL differs from the 2000 validated response receipts.')
    reused = sum(r.get('origin', {}).get('kind') == 'reused_pilot' for r in state.values())
    if reused != 250:
        raise ValueError('Expected exactly 250 original responses to be reused.')
    names = ['plan.json', 'split.json', 'conu_generations.jsonl']
    names += [f'responses/{qi:04d}-{si:02d}.json' for qi in range(100) for si in range(20)]
    hashes = {name: scoring.file_hash(root / name) for name in names}
    return records, split, plan_hash, hashes


def clean_records(records):
    output = []
    stats = {'questions': len(records), 'responses': 0, 'changed_responses': 0,
             'raw_empty_responses': 0, 'raw_responses_containing_newline': 0,
             'cleaned_equals_error': 0, 'raw_duplicate_slots': 0, 'cleaned_duplicate_slots': 0,
             'all_error_questions': 0, 'length_limited_responses': 0,
             'dropped_questions': 0, 'dropped_responses': 0}
    for record in records:
        raw = record['samples']
        if len(raw) != 20 or not all(isinstance(text, str) for text in raw):
            raise ValueError('Each question must retain exactly twenty text responses.')
        cleaned = [cleaning.filter(text) for text in raw]
        output.append({**record, 'samples_raw': list(raw), 'samples': cleaned,
                       'cleaning_policy': 'ConU exact upstream filter; all twenty slots retained'})
        stats['responses'] += len(raw)
        stats['changed_responses'] += sum(before != after for before, after in zip(raw, cleaned))
        stats['raw_empty_responses'] += sum(not text.strip() for text in raw)
        stats['raw_responses_containing_newline'] += sum('\n' in text for text in raw)
        stats['cleaned_equals_error'] += cleaned.count('error')
        stats['raw_duplicate_slots'] += len(raw) - len(set(raw))
        stats['cleaned_duplicate_slots'] += len(cleaned) - len(set(cleaned))
        stats['all_error_questions'] += int(all(text == 'error' for text in cleaned))
        stats['length_limited_responses'] += record.get('finish_reasons', []).count('length')
    return output, stats


import importlib.metadata
import os
import signal
import time
import numpy as np
import a2_conformal as conformal


def write_products(root, products):
    for name, content in products.items():
        target = root / name
        if target.is_symlink() or (target.exists() and target.read_bytes() != content):
            raise ValueError(f'Refusing to replace a different saved result: {target}')
    for name, content in products.items():
        io.atomic_write(root / name, content, immutable=True)


def clean_stage(root, records, split, plan_hash, input_hashes, upstream):
    cleaned, stats = clean_records(records)
    if stats['questions'] != 100 or stats['responses'] != 2000:
        raise ValueError('Cleaning would change the planned 100x20 counts.')
    report = {**stats, 'calibration_questions': len(split['calibration_ids']),
              'test_questions': len(split['test_ids']), 'original_responses_reused': 250,
              'new_generation_requests': 0,
              'notes': ['Exact upstream filter; no answer extraction using gold labels.',
                        'No correctness filtering, deduplication, dropping, or regeneration.',
                        'All twenty raw and cleaned slots retained in their original order.',
                        'Formatting changes do not imply incorrect original answers.'],
              'examples': [{'qid': r['qid'], 'question': r['question'], 'samples_raw': r['samples_raw'],
                            'samples_cleaned': r['samples']} for r in cleaned[:2]]}
    products = {'conu_generations.cleaned.jsonl': scoring.jsonl(cleaned),
                'cleaning_report.json': io.encode(report)}
    # Reuse byte-identical standalone cleaning output, if it already exists.
    write_products(root, products)
    certificate = {'schema': 'confqa.conu.a2_finish_cleaning.v1', 'upstream': upstream,
                   'sampling_plan_sha256': plan_hash, 'input_sha256': input_hashes,
                   'script_sha256': scoring.file_hash(Path(__file__)),
                   'questions': 100, 'responses': 2000, 'new_generation_requests': 0,
                   'outputs': {name: io.digest(content) for name, content in products.items()}}
    write_products(root, {'finish/cleaning.json': io.encode(certificate)})
    print('Cleaning complete: 100 questions, 2000 responses; all raw slots retained.', flush=True)
    return cleaned, certificate


def scalar_score(value):
    array = np.asarray(value)
    if array.size != 1:
        raise ValueError('Expected one CrossEncoder similarity value.')
    return scoring.finite_score(array.item())


def score_record(record, predict):
    samples = record['samples']
    if len(samples) != 20:
        raise ValueError('Expected all twenty answer slots.')
    texts = [record['question'] + ' ' + answer for answer in samples]
    matrix = [[1.0 if i == j else None for j in range(20)] for i in range(20)]
    for i in range(20):
        for j in range(i + 1, 20):
            matrix[i][j] = matrix[j][i] = scalar_score(predict(texts[i], texts[j]))
    gold_text = record['question'] + ' ' + record['gold_value']
    truth = [scalar_score(predict(gold_text, answer)) for answer in texts]
    return {'qid': record['qid'], 'question': record['question'], 'role': record['role'],
            'samples': list(samples), 'gold': list(record['gold']), 'canonical_gold': record['gold_value'],
            'similarity_matrix': matrix, 'similarity_to_canonical_gold': truth, 'predicted_pairs': 210}


def validate_score(saved, record, plan_hash):
    expected = {'plan_sha256': plan_hash, 'input_record_sha256': io.digest(io.encode(record)),
                'qid': record['qid'], 'question': record['question'], 'role': record['role'],
                'samples': record['samples'], 'gold': record['gold'], 'canonical_gold': record['gold_value'],
                'predicted_pairs': 210}
    if any(saved.get(key) != value for key, value in expected.items()):
        raise ValueError('A saved score belongs to a different question or plan.')
    matrix, truth = saved.get('similarity_matrix', []), saved.get('similarity_to_canonical_gold', [])
    if len(matrix) != 20 or any(len(row) != 20 for row in matrix) or len(truth) != 20:
        raise ValueError('Saved score dimensions must be 20x20 and 20.')
    for i in range(20):
        scalar_score(truth[i])
        for j in range(20):
            scalar_score(matrix[i][j])
            if matrix[i][j] != matrix[j][i] or (i == j and matrix[i][j] != 1.0):
                raise ValueError('Saved score matrix is not symmetric with diagonal one.')
    return saved


def stop_generator(project, proc_root=Path('/proc'), send_signal=os.kill, timeout=30):
    """Stop only our recorded, still identifiable completed-generation server."""
    logs = project.parent / 'logs'
    pid_file = logs / 'vllm-a1.pid'
    if not pid_file.exists():
        return
    pid = int(pid_file.read_text().strip())
    if pid <= 1:
        raise ValueError('Invalid generation-server PID; no signal sent.')
    process = proc_root / str(pid)
    if not process.exists():
        return
    try:
        if process.stat().st_uid != os.getuid():
            raise ValueError('Recorded PID belongs to another user; no signal sent.')
        command = (process / 'cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace')
        expected_model = str(project.parent / 'models/Qwen2.5-14B-Instruct')
        command_matches = 'vllm' in command.lower() and 'serve' in command and expected_model in command
        log_matches = False
        latest = logs / 'vllm-a1.latest-log'
        if latest.exists():
            log = Path(latest.read_text().strip())
            log_matches = (log.parent.resolve() == logs.resolve() and log.name.startswith('vllm-a1-')
                           and (process / 'fd/1').resolve() == log.resolve()
                           and ('vllm' in command.lower() or 'python' in command.lower()))
        if not command_matches and not log_matches:
            raise ValueError('Recorded PID no longer matches our Qwen service; no signal sent.')
        print('Stopping the completed-generation Qwen service to release model memory.', flush=True)
        send_signal(pid, signal.SIGTERM)
    except (FileNotFoundError, ProcessLookupError):
        return
    deadline = time.monotonic() + timeout
    while process.exists():
        try:
            if (process / 'status').read_text().split('State:', 1)[1].lstrip().startswith('Z'):
                return
        except FileNotFoundError:
            return
        if time.monotonic() >= deadline:
            raise ValueError('Generation server has not exited yet; saved results retained. Rerun later.')
        time.sleep(.25)


def load_predictor(model_dir):
    import torch
    # The school runtime requires allocator initialization before peak reset.
    torch.cuda.init()
    return scoring.load_predictor(model_dir)


def score_stage(project, root, records, plan, factory=load_predictor, stop=stop_generator):
    stage = root / 'finish/similarity'
    plan_hash = io.digest(io.encode(plan))
    checkpoints = {}
    for i, record in enumerate(records):
        path = stage / f'questions/{i:04d}.json'
        if path.exists():
            checkpoints[i] = validate_score(io.read_json(path), record, plan_hash)
    print(f'Scoring: {len(checkpoints)}/100 questions already complete; target 21000 pairs.', flush=True)
    predictor = runtime = stats = None
    newly_scored = 0
    started = time.monotonic()
    if len(checkpoints) < 100:
        stop(project)
    for i, record in enumerate(records):
        if i in checkpoints:
            continue
        if predictor is None:
            predictor, runtime, stats = factory(project.parent / 'models/stsb-roberta-large')
            print('Scorer device:', runtime['device'], flush=True)
        result = score_record(record, predictor)
        result.update({'plan_sha256': plan_hash, 'input_record_sha256': io.digest(io.encode(record))})
        validate_score(result, record, plan_hash)
        io.atomic_write(stage / f'questions/{i:04d}.json', io.encode(result), immutable=True)
        checkpoints[i] = result
        newly_scored += 1
        print(f'Scored question {i+1}/100 (20 answers, 210 pairs)', flush=True)
    scores = [checkpoints[i] for i in range(100)]
    content = scoring.jsonl(scores)
    manifest = {'schema': 'confqa.conu.a2_finish_similarity.v1', 'plan_sha256': plan_hash,
                'questions': 100, 'responses': 2000, 'predicted_pairs': 21000,
                'new_generation_requests': 0, 'dropped_questions': 0, 'dropped_responses': 0,
                'scores_sha256': io.digest(content),
                'checkpoints': {f'questions/{i:04d}.json': scoring.file_hash(stage / f'questions/{i:04d}.json')
                                for i in range(100)}}
    write_products(stage, {'scores.jsonl': content, 'manifest.json': io.encode(manifest)})
    if newly_scored:
        session = {'newly_scored_questions': newly_scored, 'newly_scored_pairs': 210 * newly_scored,
                   'wall_seconds': time.monotonic() - started, 'runtime': runtime,
                   'resource_stats': stats(), 'new_generation_requests': 0}
        write_products(stage, {f'sessions/{time.time_ns()}.json': io.encode(session)})
    return scores


def features(record, threshold):
    matrix = np.asarray(record['similarity_matrix'], dtype=float)
    truth = np.asarray(record['similarity_to_canonical_gold'], dtype=float)
    if (matrix.shape != (20, 20) or truth.shape != (20,) or not np.isfinite(matrix).all()
            or not np.isfinite(truth).all() or (matrix < 0).any() or (matrix > 1).any()
            or (truth < 0).any() or (truth > 1).any()):
        raise ValueError('Invalid twenty-answer similarity dimensions/values.')
    frequency = np.array([np.sum(row >= threshold) / len(row) for row in matrix])
    probability = frequency / np.sum(frequency)
    best = record['similarity_to_canonical_gold'].index(max(record['similarity_to_canonical_gold']))
    acceptable = (truth >= threshold).tolist()
    return {'qid': record['qid'], 'question': record['question'], 'role': record['role'],
            'canonical_gold': record['canonical_gold'], 'samples': list(record['samples']),
            'gold_similarity': truth.tolist(), 'acceptable_samples': acceptable,
            'has_acceptable_sample': any(acceptable), 'frequency': frequency.tolist(),
            'normalized_frequency': probability.tolist(), 'sample_nonconformity': (1 - probability).tolist(),
            'most_reliable_index': best, 'reference_nonconformity': float(1 - probability[best])}


def evaluate(scores, split, threshold=.6, alphas=(.1, .2)):
    rows = [features(record, threshold) for record in scores]
    by_id = {row['qid']: row for row in rows}
    calibration_ids, test_ids = split['calibration_ids'], split['test_ids']
    if (len(rows) != 100 or len(by_id) != 100 or len(set(calibration_ids)) != 50 or len(set(test_ids)) != 50
            or set(calibration_ids) & set(test_ids) or set(by_id) != set(calibration_ids) | set(test_ids)):
        raise ValueError('Expected exactly the frozen 100-question, disjoint 50/50 split.')
    calibration = [by_id[qid] for qid in calibration_ids]
    test = [by_id[qid] for qid in test_ids]
    if any(r['role'] != 'calibration' for r in calibration) or any(r['role'] != 'test' for r in test):
        raise ValueError('Question roles disagree with the frozen split.')
    eligible_test = [r for r in test if r['has_acceptable_sample']]
    cases = []
    for alpha in alphas:
        quantile = conformal.calibrate(calibration, alpha)
        if quantile['q_hat_is_infinite']:
            quantile['note'] = 'q_level exceeds 1; explicit +infinity selects all twenty slots.'
        sets = {r['qid']: conformal.answer_set(r, quantile) for r in rows}
        for row in rows:
            row.setdefault('prediction_sets', {})[format(alpha, '.10g')] = sets[row['qid']]
        cases.append({'calibration': quantile, 'filtered_test': conformal.metrics(eligible_test, sets),
                      'all_fixed_test_same_threshold': conformal.metrics(test, sets)})
    eligible = sum(r['has_acceptable_sample'] for r in rows)
    summary = {'schema': 'confqa.conu.a2_finish_conformal.v1', 'scope': '100-question pipeline validation',
               'questions': 100, 'responses': 2000, 'responses_per_question': 20,
               'correctness_threshold': threshold, 'alphas': list(alphas),
               'n_total': 100, 'n_applied': eligible, 'n_excluded': 100 - eligible,
               'excluded_fraction': (100 - eligible) / 100,
               'fixed_calibration_count': 50, 'fixed_test_count': 50,
               'calibration_eligible_count': sum(r['has_acceptable_sample'] for r in calibration),
               'test_eligible_count': len(eligible_test),
               'excluded_calibration_ids': [r['qid'] for r in calibration if not r['has_acceptable_sample']],
               'excluded_test_ids': [r['qid'] for r in test if not r['has_acceptable_sample']],
               'all_test_candidate_oracle_coverage': len(eligible_test) / 50, 'cases': cases,
               'notes': ['Retain all 100 questions and 2000 slots; preserve the original fixed 50/50 split.',
                         'Use the upstream active 1-normalized-frequency score and higher-quantile rule.',
                         'Keep duplicate answer slots; canonical-gold similarity >=0.6 defines acceptability.',
                         'Filtered coverage is conditional; report all fixed test questions with the same threshold too.',
                         'All-test view is not a separately unfiltered calibration experiment.',
                         'Already inspected pilot questions are included; use independent future final tests.',
                         'This completes A2 processing, not A3/A4/A5.'], 'new_generation_requests': 0}
    return rows, summary


def main(project=None, factory=load_predictor, stop=stop_generator):
    project = project or Path(__file__).resolve().parent
    root = project / sampling.CACHE_NAME
    with io.run_lock(root):
        print('A2 FINISH: verifying the existing 100 questions / 2000 responses.', flush=True)
        records, split, sampling_hash, input_hashes = validate_raw(project)
        upstream_clean = cleaning.upstream_provenance(project)
        upstream_similarity = scoring.similarity_source_provenance(project / 'third_party/ConU', cleaning.CONU_HEAD)
        upstream_criterion = conformal.criterion_source(project, cleaning.CONU_HEAD)
        cleaned, cleaning_certificate = clean_stage(root, records, split, sampling_hash, input_hashes, upstream_clean)
        plan = {'schema': 'confqa.conu.a2_finish_plan.v1', 'script_sha256': scoring.file_hash(Path(__file__)),
                'sampling_plan_sha256': sampling_hash, 'input_sha256': input_hashes, 'split': split,
                'cleaning_certificate_sha256': io.digest(io.encode(cleaning_certificate)),
                'cleaned_sha256': scoring.file_hash(root / 'conu_generations.cleaned.jsonl'),
                'upstream': {'cleaning': upstream_clean, 'similarity': upstream_similarity, 'criterion': upstream_criterion},
                'helper_sha256': {Path(m.__file__).name: scoring.file_hash(Path(m.__file__))
                                   for m in [sampling, cleaning, scoring, conformal]},
                'scorer': scoring.model_provenance(project.parent / 'models/stsb-roberta-large'),
                'packages': {name: importlib.metadata.version(name) for name in
                             ['torch', 'transformers', 'sentence-transformers', 'numpy']},
                'policy': {'question_prefix': 'question + single space + answer', 'diagonal': 1.0,
                           'upper_triangle': 'predict([qa_i,qa_j]) for i<j; mirror lower triangle',
                           'correctness': 'predict([question + canonical gold, question + cleaned sample])',
                           'activation': 'CrossEncoder default num_labels=1; no additional sigmoid',
                           'duplicates': 'preserve and score every slot', 'seed': 10, 'device': 'cuda:0',
                           'silent_truncation': False, 'correctness_threshold': .6, 'alphas': [.1, .2],
                           'new_generation_requests': 0}}
        write_products(root, {'finish/plan.json': io.encode(plan)})
        scores = score_stage(project, root, cleaned, plan, factory, stop)
        rows, summary = evaluate(scores, split)
        if (any(scoring.file_hash(root / name) != expected for name, expected in input_hashes.items())
                or scoring.file_hash(root / 'conu_generations.cleaned.jsonl') != plan['cleaned_sha256']):
            raise ValueError('Input changed during processing; final calibration output was not written.')
        summary['plan_sha256'] = io.digest(io.encode(plan))
        products = {'summary.json': io.encode(summary), 'questions.jsonl': scoring.jsonl(rows)}
        manifest = {'schema': 'confqa.conu.a2_finish_result.v1', 'plan_sha256': summary['plan_sha256'],
                    'outputs': {name: io.digest(content) for name, content in products.items()},
                    'questions_retained': 100, 'responses_retained': 2000, 'new_generation_requests': 0}
        products['manifest.json'] = io.encode(manifest)
        write_products(root / 'finish/conformal', products)
    print('A2 FINISH DONE: 100 questions, 2000 responses, 21000 similarity pairs.', flush=True)
    print('Calibration/test: 50 / 50. No new LLM answers generated.', flush=True)
    print(f"Applicable questions: {summary['n_applied']}; excluded: {summary['n_excluded']}", flush=True)
    for case in summary['cases']:
        calibration = case['calibration']
        print(f"alpha={calibration['alpha']}; status={calibration['status']}; q_hat={calibration['q_hat']}", flush=True)
        for name in ['filtered_test', 'all_fixed_test_same_threshold']:
            result = case[name]
            print(f"  {name}: n={result['n_test']}; coverage={result['coverage']}; avg_set_size={result['average_set_size_slots']}", flush=True)
    print('Result:', root / 'finish/conformal/summary.json', flush=True)


if __name__ == '__main__':
    main()


