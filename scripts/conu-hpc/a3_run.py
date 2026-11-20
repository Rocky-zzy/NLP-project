#!/usr/bin/env python3
"""A3: fixed 500 fresh TriviaQA questions x20; default plan only, --run completes all stages."""
import argparse
import gzip
import importlib.metadata
import io as streams
import json
import os
import random
import socket
import subprocess
import tarfile
import time
from pathlib import Path

import a2_100_sample as sample
import a2_100_finish as post

io = sample.pilot
data = sample.data
scoring = sample.scoring
conformal = post.conformal
N = 500
M = 20
N_CAL = 250
CACHE = 'cache/a3_500_m20'
SEED_BASE = 200000


def dependencies():
    return {Path(module.__file__).name: scoring.file_hash(Path(module.__file__))
            for module in [sample, post, data, io, scoring, scoring.cleaning, conformal]}


def select_questions(unique, demos, collision_ids, development):
    demo_ids = {r['qid'] for r in demos}
    demo_keys = {data.question_key(r['question']) for r in demos}
    pool = [r for r in sorted(unique, key=lambda r: r['qid'])
            if r['qid'] not in demo_ids and r['qid'] not in collision_ids
            and data.question_key(r['question']) not in demo_keys
            and r['question'].isascii() and r['gold_value'].isascii()]
    random.Random(0).shuffle(pool)
    if len(pool) < 100 + N or pool[:100] != development:
        raise ValueError('The source does not reproduce the frozen A2 prefix and 500 fresh A3 questions.')
    selected = pool[100:100 + N]
    if len({r['qid'] for r in selected + development + demos}) != N + 103:
        raise ValueError('A3 question IDs overlap development or few-shot examples.')
    if len({data.question_key(r['question']) for r in selected + development + demos}) != N + 103:
        raise ValueError('A3 question texts overlap development or few-shot examples.')
    qids = [r['qid'] for r in selected]
    split = {'schema': 'confqa.conu.a3_split.v1', 'selection_seed': 0,
             'generation_order': qids, 'calibration_ids': qids[:N_CAL], 'test_ids': qids[N_CAL:],
             'few_shot_ids': [r['qid'] for r in demos],
             'development_ids_excluded': [r['qid'] for r in development],
             'source_pool_slice': [100, 600], 'selection_uses_model_outcomes': False,
             'scope': '500 fresh questions; all A2 development questions excluded before generation.'}
    return selected, split


def load_source(project):
    _, _, a2_hash, _ = post.validate_raw(project)
    a2_root = project / sample.CACHE_NAME
    result = a2_root / 'finish/conformal/summary.json'
    manifest = io.read_json(a2_root / 'finish/conformal/manifest.json')
    if scoring.file_hash(result) != manifest['outputs']['summary.json']:
        raise ValueError('The completed A2 summary changed.')
    summary = io.read_json(result)
    if summary.get('questions') != 100 or summary.get('responses') != 2000:
        raise ValueError('Complete A2 100x20 before starting A3.')
    finish_plan = a2_root / 'finish/plan.json'
    finish_hash = scoring.file_hash(finish_plan)
    if (summary.get('plan_sha256') != finish_hash or manifest.get('plan_sha256') != finish_hash
            or io.read_json(finish_plan).get('script_sha256') != scoring.file_hash(Path(post.__file__))):
        raise ValueError('The A2 completed result does not match its frozen processing script/plan.')
    development, demos, _, old, bindings, upstream = sample.load_source(project)
    prefix = 'data/processed/triviaqa_a2/'
    unique = post.read_jsonl(project / prefix / 'unique_questions.jsonl')
    audit = io.read_json(project / prefix / 'source_audit.json')
    selected, split = select_questions(unique, demos,
                                       set(audit['selection_excludes_normalized_collision_ids']), development)
    a2_plan = io.read_json(a2_root / 'plan.json')
    if a2_hash != scoring.file_hash(a2_root / 'plan.json'):
        raise ValueError('A2 changed while selecting A3.')
    for name in ['plan.json', 'finish/plan.json', 'finish/conformal/summary.json', 'finish/conformal/manifest.json']:
        relative = sample.CACHE_NAME + '/' + name
        bindings[relative] = scoring.file_hash(project / relative)
    return selected, demos, split, a2_plan, bindings, upstream


def startup_path(project):
    return project.parent / 'scripts/start_vllm_a1.sh'


def build_plan(project, tokenizer_factory=sample.load_tokenizer):
    selected, demos, split, reference, bindings, upstream = load_source(project)
    model_dir = project.parent / 'models/Qwen2.5-14B-Instruct'
    for name, expected in reference['model_tokenizer_files'].items():
        if scoring.file_hash(model_dir / name) != expected:
            raise ValueError(f'Model/tokenizer file changed: {name}')
    tokenizer = tokenizer_factory(model_dir)
    if io.newline_bias(tokenizer) != reference['decode']['logit_bias']:
        raise ValueError('Tokenizer newline behavior differs from the validated A2.')
    questions = []
    calibration = set(split['calibration_ids'])
    for i, row in enumerate(selected):
        prompt = io.make_prompt(row, demos)
        ids = tokenizer.encode(prompt, add_special_tokens=True)
        if len(ids) + reference['decode']['max_new_tokens'] > reference['context_limit']:
            raise ValueError(f'Prompt exceeds the frozen context limit: {row["qid"]}')
        questions.append({**row, 'prompt': prompt, 'prompt_token_ids': ids,
                          'role': 'calibration' if row['qid'] in calibration else 'test',
                          'sample_seeds': [SEED_BASE + i * M + j for j in range(M)]})
    startup = startup_path(project)
    text = startup.read_text(encoding='utf-8')
    for flag in ['--dtype bfloat16', '--tensor-parallel-size 1', '--max-model-len 2048',
                 '--max-num-seqs 1', '--gpu-memory-utilization 0.9', '--enforce-eager',
                 'VLLM_USE_FLASHINFER_SAMPLER=0']:
        if flag not in text:
            raise ValueError(f'The existing startup script does not contain the validated setting: {flag}')
    return {'schema': 'confqa.conu.a3_sampling.500x20.v1',
            'script_sha256': scoring.file_hash(Path(__file__)), 'dependency_sha256': dependencies(),
            'input_sha256': bindings, 'upstream': upstream, 'split': split, 'questions': questions,
            **{key: reference[key] for key in ['model', 'model_path', 'model_tokenizer_files',
                                               'endpoint', 'decode', 'context_limit']},
            'num_questions': N, 'num_samples': M, 'maximum_requests': N * M,
            'reused_response_count': 0, 'startup_script_sha256': scoring.file_hash(startup),
            'packages': {name: importlib.metadata.version(name) for name in reference['packages']},
            'adaptations': ['A3 contains 500 new questions disjoint from all 100 A2 development questions.',
                            'Sort eligible source IDs, shuffle with seed 0, freeze source positions 100:600.',
                            'Keep all validated A2 prompt/model/decode settings, including TriviaQA 36 tokens.',
                            'Request seeds are 200000 + question_index*20 + sample_index.',
                            'Retain all twenty slots, including empty, duplicate, and incorrect answers.',
                            'No generation POST retries after an unknown completion status.']}


def load_state(root, plan, plan_hash):
    state = {}
    for qi in range(N):
        for si in range(M):
            path = sample.receipt_path(root, qi, si)
            if not path.exists():
                continue
            receipt = io.read_json(path)
            sample.validated_response(receipt, plan, plan_hash, qi, si)
            intent = io.read_json(root / f'attempts/{qi:04d}-{si:02d}.json')
            if (receipt.get('origin') != {'kind': 'new_generation'}
                    or intent.get('plan_sha256') != plan_hash
                    or intent.get('request_sha256') != receipt['request_sha256']
                    or intent.get('request') != sample.request_payload(plan, qi, si)):
                raise ValueError('A3 receipt differs from its recorded request intent.')
            state[(qi, si)] = receipt
    return state


def snapshot(root, plan, plan_hash, state):
    records = [post.raw_record(plan, state, i, plan_hash) for i in range(N)
               if all((i, j) in state for j in range(M))]
    content = scoring.jsonl(records)
    io.atomic_write(root / 'conu_generations.partial.jsonl', content)
    if len(records) == N:
        io.atomic_write(root / 'conu_generations.jsonl', content, immutable=True)
    io.atomic_write(root / 'progress.json', io.encode({
        'complete_questions': len(records), 'received_responses': len(state),
        'target_questions': N, 'target_responses': N * M, 'plan_sha256': plan_hash,
        'updated_at_utc': io.timestamp()}))
    return records


def prepare(project, tokenizer_factory=sample.load_tokenizer):
    plan = build_plan(project, tokenizer_factory)
    root = project / CACHE
    root.mkdir(parents=True, exist_ok=True)
    with io.run_lock(root):
        post.write_products(root, {'plan.json': io.encode(plan), 'split.json': io.encode(plan['split'])})
        state = load_state(root, plan, io.digest(io.encode(plan)))
        records = snapshot(root, plan, io.digest(io.encode(plan)), state)
    print('A3 PLAN READY: 500 fresh questions, 20 responses/question, 10000 target responses.', flush=True)
    print('A2 development excluded: 100 questions; calibration/test: 250 / 250.', flush=True)
    print(f'Already saved: {len(records)} complete questions; {len(state)} responses.', flush=True)
    print('Max input tokens:', max(len(q['prompt_token_ids']) for q in plan['questions']), flush=True)
    print('Plan:', root / 'plan.json', flush=True)
    return plan, root


def ensure_server(project, plan, root, timeout=600):
    try:
        with socket.create_connection(('127.0.0.1', 8000), timeout=1):
            listening = True
    except OSError:
        listening = False
    started = False
    if not listening:
        startup = startup_path(project)
        if scoring.file_hash(startup) != plan['startup_script_sha256']:
            raise ValueError('The startup script changed after planning.')
        env = dict(os.environ, A1_ROOT=str(project.parent), A1_ENV_DIR=str(project.parent / 'envs/confqa'),
                   A1_MODEL_DIR=str(project.parent / 'models/Qwen2.5-14B-Instruct'), A1_PORT='8000')
        subprocess.run(['bash', str(startup)], env=env, check=True)
        started = True
    deadline = time.monotonic() + timeout
    last_error = None
    while time.monotonic() < deadline:
        try:
            io.check_server(plan, root)
            print('Generation service ready.', flush=True)
            return
        except ValueError:
            raise  # Wrong model or unsupported fields is not a startup delay.
        except Exception as error:
            last_error = error
        if started:
            pid_file = project.parent / 'logs/vllm-a1.pid'
            if pid_file.exists():
                try:
                    os.kill(int(pid_file.read_text().strip()), 0)
                except ProcessLookupError:
                    raise RuntimeError('Qwen startup exited. Inspect the latest vllm-a1 log; no generation was sent.') from last_error
        print('Waiting for Qwen startup...', flush=True)
        time.sleep(5)
    raise RuntimeError(f'Qwen did not become ready; no generation was sent. Last error: {last_error}')


def generate_phase(project, plan, root, limit_questions=None, send=io.local_http, server=ensure_server):
    limit = N if limit_questions is None else limit_questions
    if not 1 <= limit <= N:
        raise ValueError('The question limit must be between 1 and 500.')
    plan_hash = io.digest(io.encode(plan))
    state = load_state(root, plan, plan_hash)
    for qi in range(limit):
        for si in range(M):
            if (qi, si) not in state and (root / f'attempts/{qi:04d}-{si:02d}.json').exists():
                raise ValueError('An unresolved previous generation exists; no automatic POST retry was sent.')
    if any((i, j) not in state for i in range(limit) for j in range(M)):
        server(project, plan, root)
    for qi in range(limit):
        for si in range(M):
            if sample.generate_one(root, plan, plan_hash, state, qi, si, send):
                print(f'Saved A3 question {qi+1}/500, answer {si+1}/20', flush=True)
        if qi == 0 or (qi + 1) % 10 == 0 or qi + 1 == limit:
            snapshot(root, plan, plan_hash, state)
    records = snapshot(root, plan, plan_hash, state)
    if len(records) != N:
        print(f'A3 PAUSED AT LIMIT: {len(records)}/500 complete questions; {len(state)} responses.', flush=True)
        return None
    print('A3 GENERATION DONE: 500 questions, 10000 responses.', flush=True)
    return records


def evaluate(scores, split):
    rows = [post.features(record, .6) for record in scores]
    by_id = {r['qid']: r for r in rows}
    cal_ids, test_ids = split['calibration_ids'], split['test_ids']
    if (len(rows) != N or len(by_id) != N or len(set(cal_ids)) != N_CAL
            or len(set(test_ids)) != N - N_CAL or set(cal_ids) & set(test_ids)
            or set(by_id) != set(cal_ids) | set(test_ids)):
        raise ValueError('A3 scores do not match the fixed disjoint 250/250 split.')
    calibration, test = [by_id[q] for q in cal_ids], [by_id[q] for q in test_ids]
    if any(r['role'] != 'calibration' for r in calibration) or any(r['role'] != 'test' for r in test):
        raise ValueError('A3 roles changed.')
    eligible_test = [r for r in test if r['has_acceptable_sample']]
    cases = []
    for alpha in [.1, .2]:
        quantile = conformal.calibrate(calibration, alpha)
        if quantile['q_hat_is_infinite']:
            quantile['note'] = 'Explicit +infinity selects all twenty slots for small calibration subsets.'
        sets = {r['qid']: conformal.answer_set(r, quantile) for r in rows}
        for row in rows:
            row.setdefault('prediction_sets', {})[str(alpha)] = sets[row['qid']]
        cases.append({'calibration': quantile, 'filtered_test': conformal.metrics(eligible_test, sets),
                      'all_fixed_test_same_threshold': conformal.metrics(test, sets)})
    applicable = sum(r['has_acceptable_sample'] for r in rows)
    summary = {'schema': 'confqa.conu.a3_result.v1', 'questions': N, 'responses': N * M,
               'responses_per_question': M, 'correctness_threshold': .6, 'alphas': [.1, .2],
               'n_total': N, 'n_applied': applicable, 'n_excluded': N - applicable,
               'excluded_fraction': (N - applicable) / N,
               'fixed_calibration_count': N_CAL, 'fixed_test_count': N - N_CAL,
               'calibration_eligible_count': sum(r['has_acceptable_sample'] for r in calibration),
               'test_eligible_count': len(eligible_test),
               'excluded_calibration_ids': [r['qid'] for r in calibration if not r['has_acceptable_sample']],
               'excluded_test_ids': [r['qid'] for r in test if not r['has_acceptable_sample']],
               'all_test_candidate_oracle_coverage': len(eligible_test) / len(test), 'cases': cases,
               'notes': ['All 500 question IDs and both partitions were frozen before generation.',
                         'All 100 A2 development question IDs/texts are excluded.',
                         'Exact upstream active frequency score and higher-quantile rule.',
                         'Fixed partitions: apply the acceptable-answer condition inside each partition.',
                         'All-fixed-test view reuses filtered-calibration thresholds; it is not the A4 unfiltered calibration.',
                         'Set sizes count slots, including duplicate text; correctness is CrossEncoder similarity.'],
               'new_generation_requests_in_postprocessing': 0}
    return rows, summary


def score_phase(project, root, records, plan, factory=post.load_predictor, stop=post.stop_generator):
    stage = root / 'similarity'
    plan_hash = io.digest(io.encode(plan))
    saved = {}
    for i, record in enumerate(records):
        path = stage / f'questions/{i:04d}.json'
        if path.exists():
            saved[i] = post.validate_score(io.read_json(path), record, plan_hash)
    print(f'A3 scoring: {len(saved)}/500 already saved; target 105000 pairs.', flush=True)
    predict = runtime = stats = None
    started = time.monotonic()
    newly_scored = 0
    if len(saved) != N:
        stop(project)
    for i, record in enumerate(records):
        if i in saved:
            continue
        if predict is None:
            predict, runtime, stats = factory(project.parent / 'models/stsb-roberta-large')
            print('Scorer device:', runtime['device'], flush=True)
        result = post.score_record(record, predict)
        result.update({'plan_sha256': plan_hash, 'input_record_sha256': io.digest(io.encode(record))})
        post.validate_score(result, record, plan_hash)
        io.atomic_write(stage / f'questions/{i:04d}.json', io.encode(result), immutable=True)
        saved[i] = result
        newly_scored += 1
        print(f'Scored A3 question {i+1}/500 (20 answers, 210 pairs)', flush=True)
    scores = [saved[i] for i in range(N)]
    content = scoring.jsonl(scores)
    manifest = {'schema': 'confqa.conu.a3_similarity.v1', 'plan_sha256': plan_hash,
                'questions': N, 'responses': N * M, 'predicted_pairs': N * 210,
                'scores_sha256': io.digest(content), 'new_generation_requests': 0,
                'checkpoints': {f'questions/{i:04d}.json': scoring.file_hash(stage / f'questions/{i:04d}.json')
                                for i in range(N)}}
    post.write_products(stage, {'scores.jsonl': content, 'manifest.json': io.encode(manifest)})
    if newly_scored:
        post.write_products(stage, {f'sessions/{time.time_ns()}.json': io.encode({
            'newly_scored_questions': newly_scored, 'newly_scored_pairs': newly_scored * 210,
            'wall_seconds': time.monotonic() - started, 'runtime': runtime, 'resource_stats': stats()})})
    return scores


def ascii_jsonl(records):
    return ''.join(json.dumps(r, ensure_ascii=True, sort_keys=True, allow_nan=False) + '\n' for r in records).encode()


def handoff(project, root, plan, cleaned, scores, features, summary):
    generations = [{**record, 'seed': record['sample_seeds'][0], 'selection_seed': 0} for record in cleaned]
    score_rows = [{**score, 'scores': row['sample_nonconformity'], 'sim_to_gold': row['gold_similarity'],
                   'is_correct': row['acceptable_samples'], 'correctness_threshold': .6,
                   'similarity_frequency_threshold': .6, 'score_definition': '1 - normalized similarity frequency'}
                  for score, row in zip(scores, features)]
    prefix = project / 'data/processed/triviaqa_a2'
    selection = {**plan['split'], 'source_audit': io.read_json(prefix / 'source_audit.json')}
    reproduce = '''import json, random, unicodedata
from pathlib import Path
root = Path(__file__).resolve().parent
def lines(path):
    with path.open(encoding="utf-8") as f: return [json.loads(line) for line in f]
def key(s): return " ".join(unicodedata.normalize("NFKC", s).casefold().split())
s = json.loads((root / "source/selection.json").read_text())
demos = lines(root / "source/few_shot.jsonl")
demo_ids, demo_keys = {r["qid"] for r in demos}, {key(r["question"]) for r in demos}
collisions = set(s["source_audit"]["selection_excludes_normalized_collision_ids"])
pool = [r for r in sorted(lines(root / "source/unique_questions.jsonl"), key=lambda r:r["qid"])
        if r["qid"] not in demo_ids and r["qid"] not in collisions and key(r["question"]) not in demo_keys
        and r["question"].isascii() and r["gold_value"].isascii()]
random.Random(0).shuffle(pool)
assert [r["qid"] for r in pool[:100]] == s["development_ids_excluded"]
assert [r["qid"] for r in pool[100:600]] == s["generation_order"]
assert pool[100:600] == lines(root / "source/questions.jsonl")
print("A3 selection reproduced: 500 questions; A2 overlap: 0; calibration/test: 250/250")
'''
    source_questions = [{key: value for key, value in q.items()
                         if key not in ['prompt', 'prompt_token_ids', 'role', 'sample_seeds']} for q in plan['questions']]
    files = {'cache/conu_generations.jsonl': ascii_jsonl(generations),
             'cache/conu_scores.jsonl': ascii_jsonl(score_rows),
             'source/questions.jsonl': ascii_jsonl(source_questions),
             'source/few_shot.jsonl': (prefix / 'few_shot.jsonl').read_bytes(),
             'source/unique_questions.jsonl': (prefix / 'unique_questions.jsonl').read_bytes(),
             'source/selection.json': io.encode(selection),
             'results/summary.json': io.encode(summary), 'reproduce_selection.py': reproduce.encode(),
             'configs/a3_run.json': io.encode({key: plan[key] for key in
                  ['model', 'decode', 'context_limit', 'num_questions', 'num_samples', 'split', 'packages']}),
             'README.md': ('# A3 ConU handoff\n\n500 fixed fresh questions, 20 slots each.\n'
                  'Run `python reproduce_selection.py` to reproduce all qids without a GPU.\n'
                  '`cache/conu_generations.jsonl`: samples are cleaned; samples_raw retains originals.\n'
                  '`cache/conu_scores.jsonl`: scores are 1-normalized-frequency; sim_to_gold and is_correct retain canonical-gold checks.\n'
                  'Duplicates and incorrect/empty answers are retained. No weights or environment binaries are included.\n'
                  'Filtered metrics are conditional; the all-test view uses the same filtered-calibration threshold.\n').encode()}
    files['manifest.json'] = io.encode({'schema': 'confqa.conu.a3_handoff.v1', 'questions': N, 'samples_per_question': M,
                                      'files': {name: io.digest(content) for name, content in files.items()}})
    post.write_products(root / 'handoff', files)
    buffer = streams.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w') as archive:
        for name, content in sorted(files.items()):
            info = tarfile.TarInfo(name)
            info.size, info.mtime, info.mode = len(content), 0, 0o644
            archive.addfile(info, streams.BytesIO(content))
    io.atomic_write(root / 'a3_handoff.tar.gz', gzip.compress(buffer.getvalue(), mtime=0), immutable=True)


def run(project, plan, root, limit_questions=None, send=io.local_http, server=ensure_server,
        factory=post.load_predictor, stop=post.stop_generator):
    with io.run_lock(root):
        if scoring.file_hash(root / 'plan.json') != io.digest(io.encode(plan)):
            raise ValueError('The saved A3 plan changed.')
        if any(scoring.file_hash(project / name) != expected for name, expected in plan['input_sha256'].items()):
            raise ValueError('A frozen input changed before A3 generation.')
        # Check both downstream sources and model files before spending the generation budget.
        processing = {'schema': 'confqa.conu.a3_processing_plan.v1',
                      'sampling_plan_sha256': scoring.file_hash(root / 'plan.json'),
                      'script_sha256': scoring.file_hash(Path(__file__)), 'dependency_sha256': dependencies(),
                      'scorer': scoring.model_provenance(project.parent / 'models/stsb-roberta-large'),
                      'similarity_source': scoring.similarity_source_provenance(project / 'third_party/ConU', post.cleaning.CONU_HEAD),
                      'criterion_source': conformal.criterion_source(project, post.cleaning.CONU_HEAD),
                      'correctness_threshold': .6, 'alphas': [.1, .2],
                      'packages': {name: importlib.metadata.version(name) for name in
                                   ['torch', 'transformers', 'sentence-transformers', 'numpy']}}
        post.write_products(root, {'processing_plan.json': io.encode(processing)})
        records = generate_phase(project, plan, root, limit_questions, send, server)
        if records is None:
            return
        cleaned, stats = post.clean_records(records)
        if len(cleaned) != N or stats['responses'] != N * M:
            raise ValueError('A3 cleaning changed the number of slots.')
        post.write_products(root, {'conu_generations.cleaned.jsonl': scoring.jsonl(cleaned),
                                   'cleaning_report.json': io.encode(stats)})
        processing['raw_sha256'] = scoring.file_hash(root / 'conu_generations.jsonl')
        processing['cleaned_sha256'] = scoring.file_hash(root / 'conu_generations.cleaned.jsonl')
        post.write_products(root, {'similarity/plan.json': io.encode(processing)})
        scores = score_phase(project, root, cleaned, processing, factory, stop)
        rows, summary = evaluate(scores, plan['split'])
        if (scoring.file_hash(root / 'conu_generations.jsonl') != processing['raw_sha256']
                or any(scoring.file_hash(project / name) != expected for name, expected in plan['input_sha256'].items())):
            raise ValueError('Input changed during A3; final output was not written.')
        summary['processing_plan_sha256'] = io.digest(io.encode(processing))
        result_files = {'summary.json': io.encode(summary), 'questions.jsonl': scoring.jsonl(rows)}
        result_files['manifest.json'] = io.encode({'schema': 'confqa.conu.a3_conformal_manifest.v1',
                  'outputs': {name: io.digest(content) for name, content in result_files.items()},
                  'questions_retained': N, 'responses_retained': N * M})
        post.write_products(root / 'conformal', result_files)
        handoff(project, root, plan, cleaned, scores, rows, summary)
    print('A3 DONE: 500 questions, 10000 responses, 105000 similarity pairs.', flush=True)
    print(f"Applicable: {summary['n_applied']}; excluded: {summary['n_excluded']}; calibration/test: 250 / 250", flush=True)
    for case in summary['cases']:
        print('alpha:', case['calibration']['alpha'], '; q_hat:', case['calibration']['q_hat'], flush=True)
        for name in ['filtered_test', 'all_fixed_test_same_threshold']:
            metric = case[name]
            print(f"  {name}: n={metric['n_test']}; coverage={metric['coverage']}; avg_set_size={metric['average_set_size_slots']}", flush=True)
    print('Result:', root / 'conformal/summary.json', flush=True)
    print('Handoff:', root / 'a3_handoff.tar.gz', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--limit-questions', type=int)
    args = parser.parse_args()
    project = Path(__file__).resolve().parent
    plan, root = prepare(project)
    if args.run:
        run(project, plan, root, args.limit_questions)
    else:
        print('PLAN ONLY: no service started, no generation requests sent.', flush=True)
