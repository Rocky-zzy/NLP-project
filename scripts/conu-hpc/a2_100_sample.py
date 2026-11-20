#!/usr/bin/env python3
"""Prepare A2 100x20; only --run sends generation requests to the local server."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import random
import time
from pathlib import Path

import a2_data as data
import a2_sample_fixed as pilot
import a2_score as scoring

QUESTION_COUNT = 100
SAMPLE_COUNT = 20
CACHE_NAME = 'cache/a2_100_m20'
EXTRA_SEED_BASE = 100000


def load_source(project):
    # All these functions are CPU/file operations; no tokenizer, model, or HTTP.
    _, old_questions, old_split, bindings, upstream = scoring.validate_inputs(project)
    prefix = 'data/processed/triviaqa_a2'
    preparation = pilot.read_json(project / prefix / 'manifest.json')
    for name in ['unique_questions.jsonl', 'source_audit.json']:
        relative = prefix + '/' + name
        if scoring.file_hash(project / relative) != preparation['artifacts'][relative]['sha256']:
            raise ValueError(f'Prepared source file changed: {relative}')
        bindings[relative] = scoring.file_hash(project / relative)
    source = preparation['source']['relative_path']
    if scoring.file_hash(project / source) != pilot.SOURCE_SHA256:
        raise ValueError('Original TriviaQA Parquet changed.')
    bindings[source] = pilot.SOURCE_SHA256
    # File iteration splits physical JSONL records only. str.splitlines() also
    # splits valid U+0085/U+2028/U+2029 characters inside JSON string values.
    with (project / prefix / 'unique_questions.jsonl').open(encoding='utf-8') as handle:
        unique = [json.loads(line) for line in handle]
    audit = pilot.read_json(project / prefix / 'source_audit.json')
    _, demos, _, _, _ = pilot.load_inputs(project)
    demo_ids = {row['qid'] for row in demos}
    demo_keys = {data.question_key(row['question']) for row in demos}
    collision_ids = set(audit['selection_excludes_normalized_collision_ids'])
    eligible = [row for row in sorted(unique, key=lambda row: row['qid'])
                if row['qid'] not in demo_ids and row['qid'] not in collision_ids
                and data.question_key(row['question']) not in demo_keys
                and row['question'].isascii() and row['gold_value'].isascii()]
    random.Random(0).shuffle(eligible)
    if len(eligible) < QUESTION_COUNT or eligible[:50] != old_questions:
        raise ValueError('Source selection no longer reproduces the original 50-question prefix.')
    selected = eligible[:QUESTION_COUNT]
    if len({data.question_key(row['question']) for row in selected + demos}) != QUESTION_COUNT + 3:
        raise ValueError('Question texts overlap or duplicate few-shot examples.')
    qids = [row['qid'] for row in selected]
    split = {'schema': 'confqa.conu.a2_100_split.v1', 'selection_seed': 0,
             'generation_order': qids, 'few_shot_ids': [row['qid'] for row in demos],
             'calibration_ids': old_split['calibration_ids'] + qids[50:75],
             'test_ids': old_split['test_ids'] + qids[75:100],
             'old_25_25_roles_retained': True,
             'selection_uses_model_outcomes': False,
             'scope': '100-question pipeline validation; reserve independent unseen tests for later main-study design.'}
    if (len(set(split['calibration_ids'])) != 50 or len(set(split['test_ids'])) != 50
            or set(split['calibration_ids']) & set(split['test_ids'])
            or set(split['calibration_ids']) | set(split['test_ids']) != set(qids)):
        raise ValueError('Invalid 50/50 calibration/test partition.')
    old_root = project / 'cache/a2_conu_pilot_v2'
    old_plan = pilot.read_json(old_root / 'plan.json')
    return selected, demos, split, old_plan, bindings, upstream


def load_tokenizer(model_dir):
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained(str(model_dir), local_files_only=True,
                                        use_fast=False, trust_remote_code=False)


def request_payload(plan, qi, si):
    # The tested vLLM protocol is unchanged; only number of slots is expanded.
    return pilot.request_payload(plan, qi, si)


def validated_response(receipt, plan, plan_hash, qi, si):
    expected_hash = pilot.digest(pilot.encode(request_payload(plan, qi, si)))
    if (receipt.get('plan_sha256') != plan_hash or receipt.get('request_sha256') != expected_hash
            or receipt.get('qid') != plan['questions'][qi]['qid'] or receipt.get('sample_index') != si):
        raise ValueError(f'Response plan/request/slot mismatch at {qi}/{si}.')
    body = receipt.get('response', {})
    choices = body.get('choices', [])
    if (body.get('model') != plan['model'] or len(choices) != 1
            or choices[0].get('index') != 0 or not isinstance(choices[0].get('text'), str)
            or choices[0].get('finish_reason') not in ('stop', 'length')):
        raise ValueError(f'Invalid model response at {qi}/{si}.')
    return choices[0]['text']


def receipt_path(root, qi, si):
    return root / 'responses' / f'{qi:04d}-{si:02d}.json'


def build_plan(project, tokenizer_factory=load_tokenizer):
    selected, demos, split, old, bindings, upstream = load_source(project)
    model_dir = project.parent / 'models/Qwen2.5-14B-Instruct'
    for name, expected in old['model_tokenizer_files'].items():
        if scoring.file_hash(model_dir / name) != expected:
            raise ValueError(f'Model/tokenizer file changed: {name}')
    tokenizer = tokenizer_factory(model_dir)
    if pilot.newline_bias(tokenizer) != old['decode']['logit_bias']:
        raise ValueError('Newline tokenization differs from the validated pilot.')
    if old['model'] != pilot.MODEL or old['decode']['max_new_tokens'] != 36:
        raise ValueError('Unexpected pilot model or TriviaQA output length.')
    calibration = set(split['calibration_ids'])
    planned, imports = [], {}
    for qi, row in enumerate(selected):
        prompt = pilot.make_prompt(row, demos)
        token_ids = tokenizer.encode(prompt, add_special_tokens=True)
        if len(token_ids) + old['decode']['max_new_tokens'] > old['context_limit']:
            raise ValueError(f'Prompt exceeds the existing context limit: {row["qid"]}')
        seeds = [EXTRA_SEED_BASE + qi * SAMPLE_COUNT + si for si in range(SAMPLE_COUNT)]
        if qi < 50:
            previous = old['questions'][qi]
            if (previous['qid'] != row['qid'] or previous['prompt'] != prompt
                    or previous['prompt_token_ids'] != token_ids):
                raise ValueError('Existing prompt differs; original responses cannot be reused.')
            seeds[:5] = previous['sample_seeds']
        if len(seeds) != SAMPLE_COUNT or len(set(seeds)) != SAMPLE_COUNT:
            raise ValueError('Each question must have twenty distinct recorded request seeds.')
        planned.append({**row, 'prompt': prompt, 'prompt_token_ids': token_ids,
                        'role': 'calibration' if row['qid'] in calibration else 'test',
                        'sample_seeds': seeds})
        if qi < 50:
            for si in range(5):
                name = f'{qi:04d}-{si:02d}.json'
                relative = f'cache/a2_conu_pilot_v2/responses/{name}'
                imports[name] = {'file': relative, 'sha256': scoring.file_hash(project / relative)}
    dependencies = {Path(module.__file__).name: scoring.file_hash(Path(module.__file__))
                    for module in [data, pilot, scoring, scoring.cleaning]}
    return {'schema': 'confqa.conu.a2_sampling.100x20.v1',
            'script_sha256': scoring.file_hash(Path(__file__)), 'dependency_sha256': dependencies,
            'input_sha256': bindings, 'upstream': upstream,
            'model': old['model'], 'model_path': old['model_path'],
            'model_tokenizer_files': old['model_tokenizer_files'], 'endpoint': old['endpoint'],
            'decode': old['decode'], 'context_limit': old['context_limit'],
            'num_questions': QUESTION_COUNT, 'num_samples': SAMPLE_COUNT,
            'maximum_requests': QUESTION_COUNT * SAMPLE_COUNT,
            'reused_response_count': 250, 'maximum_new_requests': 1750,
            'old_plan_sha256': pilot.digest(pilot.encode(old)),
            'reused_receipts': imports, 'split': split, 'questions': planned,
            'packages': {name: importlib.metadata.version(name) for name in old['packages']},
            'adaptations': [
                'User-confirmed A2 size: 100 questions and 20 answers per question.',
                'Original 50 questions are the deterministic prefix; preserve their existing 25/25 roles.',
                'New question selection depends only on source metadata, never model correctness.',
                'Reuse each original first-five response only after exact prompt/token/decode/seed request comparison.',
                'Keep the validated 36-token TriviaQA limit, which upstream overrides despite the shared YAML generic 32-token value.',
                'Keep validated plain three-shot prompt, seven bad_words and newline token-198 bias; all decode settings unchanged.',
                'New slots use seed 100000 + question_index*20 + sample_index; reused seeds remain original.',
                'New cache is separate; do not alter any pilot files or their immutable plans.',
                'This A2 is a pipeline-validation set, including already inspected pilot outcomes; do not treat it as a fresh final test.',
            ]}


def imported_receipt(project, plan, plan_hash, old_plan, qi, si):
    name = f'{qi:04d}-{si:02d}.json'
    provenance = plan['reused_receipts'][name]
    source_path = project / provenance['file']
    if scoring.file_hash(source_path) != provenance['sha256']:
        raise ValueError('An original response changed; refusing reuse.')
    source = pilot.read_json(source_path)
    pilot.response_text(source, old_plan, qi, si)
    payload = request_payload(plan, qi, si)
    if payload != pilot.request_payload(old_plan, qi, si):
        raise ValueError('New planned request is not identical to the saved original request.')
    return {'plan_sha256': plan_hash, 'request_sha256': pilot.digest(pilot.encode(payload)),
            'qid': plan['questions'][qi]['qid'], 'sample_index': si,
            'requested_at_utc': source['requested_at_utc'], 'elapsed_seconds': 0.0,
            'response': source['response'], 'origin': {'kind': 'reused_pilot', **provenance,
                'original_plan_sha256': source['plan_sha256'],
                'original_elapsed_seconds': source.get('elapsed_seconds')}}


def load_saved(project, plan, root, plan_hash):
    state = {}
    for qi in range(QUESTION_COUNT):
        for si in range(SAMPLE_COUNT):
            path = receipt_path(root, qi, si)
            if not path.exists():
                continue
            receipt = pilot.read_json(path)
            validated_response(receipt, plan, plan_hash, qi, si)
            name = path.name
            if name in plan['reused_receipts']:
                expected = plan['reused_receipts'][name]
                origin = receipt.get('origin', {})
                if origin.get('kind') != 'reused_pilot' or any(origin.get(k) != v for k, v in expected.items()):
                    raise ValueError('Imported response lost its provenance.')
                original = pilot.read_json(project / expected['file'])
                if scoring.file_hash(project / expected['file']) != expected['sha256'] or receipt['response'] != original['response']:
                    raise ValueError('Imported response differs from the original raw response.')
            else:
                intent = pilot.read_json(root / 'attempts' / name)
                if (receipt.get('origin') != {'kind': 'new_generation'}
                        or intent.get('plan_sha256') != plan_hash or intent.get('request_sha256') != receipt['request_sha256']
                        or intent.get('request') != request_payload(plan, qi, si)):
                    raise ValueError('Generated response differs from its saved request intent.')
            state[(qi, si)] = receipt
    return state


def save_snapshot(root, plan, plan_hash, state):
    records = []
    for qi, question in enumerate(plan['questions']):
        if not all((qi, si) in state for si in range(SAMPLE_COUNT)):
            continue
        receipts = [state[(qi, si)] for si in range(SAMPLE_COUNT)]
        records.append({**{key: question[key] for key in ['qid', 'question', 'gold_value', 'gold', 'role', 'prompt', 'sample_seeds']},
                        'samples': [receipt['response']['choices'][0]['text'] for receipt in receipts],
                        'model': plan['model'], 'decode': plan['decode'],
                        'finish_reasons': [receipt['response']['choices'][0]['finish_reason'] for receipt in receipts],
                        'usage_per_sample': [receipt['response'].get('usage') for receipt in receipts],
                        'raw_response_files': [f'responses/{qi:04d}-{si:02d}.json' for si in range(SAMPLE_COUNT)],
                        'reused_sample_indices': [si for si, receipt in enumerate(receipts) if receipt.get('origin', {}).get('kind') == 'reused_pilot'],
                        'sampling_plan_sha256': plan_hash})
    encoded = scoring.jsonl(records)
    pilot.atomic_write(root / 'conu_generations.partial.jsonl', encoded)
    if len(records) == QUESTION_COUNT:
        pilot.atomic_write(root / 'conu_generations.jsonl', encoded, immutable=True)
    reused = sum(receipt.get('origin', {}).get('kind') == 'reused_pilot' for receipt in state.values())
    pilot.atomic_write(root / 'progress.json', pilot.encode({
        'updated_at_utc': pilot.timestamp(), 'plan_sha256': plan_hash,
        'complete_questions': len(records), 'received_responses': len(state),
        'reused_responses': reused, 'new_saved_responses': len(state) - reused,
        'target_questions': QUESTION_COUNT, 'target_responses': QUESTION_COUNT * SAMPLE_COUNT}))
    return len(records)


def prepare(project, tokenizer_factory=load_tokenizer):
    plan = build_plan(project, tokenizer_factory)
    root = project / CACHE_NAME
    root.mkdir(parents=True, exist_ok=True)
    plan_hash = pilot.digest(pilot.encode(plan))
    old_plan = pilot.read_json(project / 'cache/a2_conu_pilot_v2/plan.json')
    with pilot.run_lock(root):
        pilot.atomic_write(root / 'plan.json', pilot.encode(plan), immutable=True)
        pilot.atomic_write(root / 'split.json', pilot.encode(plan['split']), immutable=True)
        for qi in range(50):
            for si in range(5):
                receipt = imported_receipt(project, plan, plan_hash, old_plan, qi, si)
                pilot.atomic_write(receipt_path(root, qi, si), pilot.encode(receipt), immutable=True)
        state = load_saved(project, plan, root, plan_hash)
        completed = save_snapshot(root, plan, plan_hash, state)
    print('A2 100 PLAN READY', flush=True)
    print('Questions: 100; responses/question: 20; target responses: 2000', flush=True)
    print('Original responses reused: 250; maximum new generation requests: 1750', flush=True)
    print('Calibration/test: 50 / 50; original pilot roles retained.', flush=True)
    print('Already complete questions:', completed, '; saved responses:', len(state), flush=True)
    print('Max input tokens:', max(len(q['prompt_token_ids']) for q in plan['questions']), flush=True)
    print('Plan:', root / 'plan.json', flush=True)
    return plan, root


def generate_one(root, plan, plan_hash, state, qi, si, send):
    key = (qi, si)
    if key in state:
        return False
    name = f'{qi:04d}-{si:02d}.json'
    intent_path = root / 'attempts' / name
    if intent_path.exists():
        raise ValueError(f'Previous request has no saved reply: {name}. No automatic retry was sent.')
    payload = request_payload(plan, qi, si)
    intent = {'plan_sha256': plan_hash, 'request_sha256': pilot.digest(pilot.encode(payload)),
              'qid': plan['questions'][qi]['qid'], 'sample_index': si,
              'requested_at_utc': pilot.timestamp(), 'request': payload}
    pilot.atomic_write(intent_path, pilot.encode(intent), immutable=True)
    started = time.monotonic()
    try:
        body = send('/v1/completions', payload, timeout=180)
        receipt = {key: value for key, value in intent.items() if key != 'request'}
        receipt.update({'response': body, 'elapsed_seconds': time.monotonic() - started,
                        'origin': {'kind': 'new_generation'}})
        # Save even an invalid model envelope for diagnosis; never silently POST again.
        pilot.atomic_write(receipt_path(root, qi, si), pilot.encode(receipt), immutable=True)
        validated_response(receipt, plan, plan_hash, qi, si)
    except Exception as error:
        pilot.atomic_write(root / 'errors' / name, pilot.encode({
            'request': intent, 'error': str(error), 'recorded_at_utc': pilot.timestamp()}), immutable=True)
        raise
    state[(qi, si)] = receipt
    return True


def run(project, plan, root, limit_questions=None, send=pilot.local_http, check=pilot.check_server):
    limit = QUESTION_COUNT if limit_questions is None else limit_questions
    if not 1 <= limit <= QUESTION_COUNT:
        raise ValueError('Question limit must be between 1 and 100.')
    plan_hash = pilot.digest(pilot.encode(plan))
    with pilot.run_lock(root):
        if scoring.file_hash(root / 'plan.json') != plan_hash:
            raise ValueError('Saved plan changed before generation.')
        state = load_saved(project, plan, root, plan_hash)
        for qi in range(limit):
            for si in range(SAMPLE_COUNT):
                if (qi, si) not in state and (root / f'attempts/{qi:04d}-{si:02d}.json').exists():
                    raise ValueError('An unresolved earlier request exists; no automatic retry or generation was sent.')
        needed = [(qi, si) for qi in range(limit) for si in range(SAMPLE_COUNT) if (qi, si) not in state]
        if needed:
            check(plan, root)
        for qi in range(limit):
            for si in range(SAMPLE_COUNT):
                if generate_one(root, plan, plan_hash, state, qi, si, send):
                    print(f'Saved question {qi+1}/100, answer {si+1}/20', flush=True)
            # Maintain in-memory state; no repeated filesystem-wide receipt scan.
            if qi == 0 or (qi + 1) % 5 == 0 or qi + 1 == limit:
                save_snapshot(root, plan, plan_hash, state)
        completed = save_snapshot(root, plan, plan_hash, state)
        if completed == QUESTION_COUNT:
            print('A2 100 SAMPLING DONE: 100 questions, 2000 responses (250 reused).', flush=True)
            print('Output:', root / 'conu_generations.jsonl', flush=True)
        else:
            print(f'A2 100 SAMPLING PAUSED AT LIMIT: {completed}/100 complete questions; {len(state)} saved responses.', flush=True)
            print('Rerun --run without --limit-questions to continue; saved responses will be reused.', flush=True)


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
        print('PLAN ONLY: no model service started and no generation requests sent.', flush=True)
