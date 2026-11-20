#!/usr/bin/env python3
"""Verify and clean the completed 50x5 pilot on CPU, retaining every raw response."""
import ast
import json
import subprocess
from pathlib import Path

import a2_sample_fixed as sampling

CONU_HEAD = "c0c450e8dbef489cfed28f585f1a4ddf0e66078b"
FILTER_AST_SHA256 = "052dfbc73fc6093b9ee78be337629608713fac56dbfc23f3d42d00b156391b8e"


# Exact upstream filter, including its existing decimal/ASCII/sentinel behavior.
def filter(text):
    text = text.strip()
    strings_to_filter_on = ['\n', '.', '#']
    while '.' in text:
        point_idx = text.index('.')
        if point_idx != len(text) - 1 and text[point_idx - 1].isdigit() and text[point_idx + 1].isdigit():
            text = text.replace('.', '(dp)', 1)
        else:
            break
    for string in strings_to_filter_on:
        if string in text:
            text = text.split(string)[0]
    if '(dp)' in text:
        text = text.replace('(dp)', '.')
    new_text = ''
    if len(text) != 0:
        for ch in text:
            if ch.isascii():
                new_text += ch
    if len(new_text) == 0:
        new_text = 'error'
    return new_text


def filter_hash(source):
    nodes = [node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name == 'filter']
    if len(nodes) != 1:
        raise ValueError('Expected exactly one upstream filter function.')
    node = nodes[0]
    # Python 3.12 adds empty FunctionDef.type_params; the school environment is 3.11.
    if getattr(node, 'type_params', []):
        raise ValueError('Unexpected generic filter function.')
    node._fields = tuple(field for field in node._fields if field != 'type_params')
    return sampling.digest(ast.dump(node, include_attributes=False).encode('utf-8'))


def upstream_provenance(project):
    repository = project / 'third_party/ConU'
    actual_head = subprocess.run(['git', '-C', str(repository), 'rev-parse', 'HEAD'],
                                 check=True, text=True, capture_output=True).stdout.strip()
    if actual_head != CONU_HEAD:
        raise ValueError('ConU revision differs from the fixed experiment revision.')
    source_path = repository / 'clean_open_domain_qa.py'
    source = source_path.read_bytes()
    if filter_hash(source.decode('utf-8')) != FILTER_AST_SHA256:
        raise ValueError('Upstream filter changed; no cleaning was performed.')
    if filter_hash(Path(__file__).read_text(encoding='utf-8')) != FILTER_AST_SHA256:
        raise ValueError('Local filter is not identical to the pinned upstream function.')
    return {'git_head': actual_head, 'script': 'third_party/ConU/clean_open_domain_qa.py',
            'script_sha256': sampling.digest(source), 'filter_ast_sha256': FILTER_AST_SHA256}


def clean_records(records):
    output = []
    stats = {'questions': len(records), 'responses': 0, 'changed_responses': 0,
             'raw_empty_responses': 0, 'raw_responses_containing_newline': 0,
             'cleaned_equals_error': 0, 'raw_duplicate_slots': 0, 'cleaned_duplicate_slots': 0,
             'all_error_questions': 0, 'length_limited_responses': 0,
             'dropped_questions': 0, 'dropped_responses': 0}
    for record in records:
        raw = record['samples']
        if len(raw) != 5 or not all(isinstance(text, str) for text in raw):
            raise ValueError('Each question must retain exactly five text responses.')
        cleaned = [filter(text) for text in raw]
        output.append({**record, 'samples_raw': list(raw), 'samples': cleaned,
                       'cleaning_policy': 'ConU exact upstream filter; all five slots retained'})
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


def main(project=None):
    project = project or Path(__file__).resolve().parent
    cache = project / 'cache/a2_conu_pilot_v2'
    raw_path = cache / 'conu_generations.jsonl'
    raw_bytes = raw_path.read_bytes()
    raw_sha = sampling.digest(raw_bytes)
    records = [json.loads(line) for line in raw_bytes.decode('utf-8').splitlines()]
    plan = sampling.read_json(cache / 'plan.json')
    if plan.get('schema') != 'confqa.conu.a2_sampling.v2' or plan.get('num_questions') != 50 or plan.get('num_samples') != 5:
        raise ValueError('Expected the completed fixed 50-question, five-response v2 pilot.')
    if sampling.digest(Path(sampling.__file__).read_bytes()) != plan['script_sha256']:
        raise ValueError('Sampling script differs from the one recorded in the plan.')
    questions, _, split, _, preparation_hash = sampling.load_inputs(project)
    if preparation_hash != plan['preparation_manifest_sha256']:
        raise ValueError('Prepared data provenance changed.')
    if [record['qid'] for record in records] != [record['qid'] for record in questions]:
        raise ValueError('Generated question order differs from the frozen input.')
    expected, received = sampling.collect(cache, plan)
    if len(expected) != 50 or received != 250 or records != expected:
        raise ValueError('Final JSONL differs from the complete validated raw response cache.')
    upstream = upstream_provenance(project)
    cleaned, stats = clean_records(records)
    if stats['questions'] != 50 or stats['responses'] != 250:
        raise ValueError('Cleaning would change the planned counts.')
    cleaned_bytes = ''.join(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n' for row in cleaned).encode('utf-8')
    report = {**stats, 'calibration_questions': len(split['calibration_ids']), 'test_questions': len(split['test_ids']),
              'notes': [
                  'No answer extraction using gold labels, no correctness filtering, and no deduplication.',
                  'Literal upstream error sentinel is counted without claiming every such answer was originally empty.',
                  'The exact upstream filter can truncate abbreviations/periods and retains its leading-decimal indexing behavior.',
                  'Complete first sentences remain complete sentences; non-ASCII characters are removed as in upstream.',
                  'Gold aliases are copied unchanged from the source; cleaning does not establish correctness.',
              ],
              'examples': [{'qid': row['qid'], 'question': row['question'], 'samples_raw': row['samples_raw'],
                            'samples_cleaned': row['samples']} for row in cleaned[:2]]}
    products = {'conu_generations.cleaned.jsonl': cleaned_bytes, 'cleaning_report.json': sampling.encode(report)}
    manifest = {'schema': 'confqa.conu.a2_cleaning.v1', 'upstream': upstream,
                'script_sha256': sampling.digest(Path(__file__).read_bytes()),
                'input': {'file': raw_path.name, 'sha256': raw_sha},
                'sampling_plan_sha256': sampling.digest((cache / 'plan.json').read_bytes()),
                'prepared_manifest_sha256': preparation_hash,
                'split_sha256': sampling.digest((project / 'data/splits/triviaqa_a2_pilot.json').read_bytes()),
                'outputs': {name: {'sha256': sampling.digest(content)} for name, content in products.items()},
                'questions': 50, 'responses': 250, 'new_generation_requests': 0,
                'sample_policy': 'Retain raw text in samples_raw and cleaned text in samples, in original order.'}
    products['cleaning_manifest.json'] = sampling.encode(manifest)
    for name, content in products.items():
        target = cache / name
        if target.is_symlink() or (target.exists() and target.read_bytes() != content):
            raise ValueError(f'Refusing to replace different existing cleaning output: {target}')
    if sampling.digest(raw_path.read_bytes()) != raw_sha:
        raise ValueError('Raw input changed during cleaning; no output written.')
    for name, content in products.items():
        sampling.atomic_write(cache / name, content, immutable=True)
    print('A2 CLEANING DONE')
    print('Questions:', stats['questions'], '; responses:', stats['responses'])
    print('Changed responses:', stats['changed_responses'])
    print('Raw empty:', stats['raw_empty_responses'], '; cleaned equals error:', stats['cleaned_equals_error'])
    print('Dropped questions: 0; dropped responses: 0')
    print('Output:', cache / 'conu_generations.cleaned.jsonl')
    for example in report['examples']:
        print('Q:', example['question'])
        print('Cleaned:', json.dumps(example['samples_cleaned'], ensure_ascii=False))
    print('CPU only. Raw responses retained. No model loaded or queried.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        raise SystemExit(f'ERROR: {error}') from error
