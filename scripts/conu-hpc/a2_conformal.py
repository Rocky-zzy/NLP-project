#!/usr/bin/env python3
"""Calibrate and evaluate the completed 50x5 A2 pilot on CPU only."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import subprocess
from pathlib import Path

import numpy as np

import a2_score as scoring
import a2_sample_fixed as io


def criterion_source(project, revision):
    repository = project / 'third_party/ConU'
    name = 'conformal_uncertainty_criterion.py'
    reference = subprocess.run(['git', '-C', str(repository), 'show', f'{revision}:{name}'],
                               check=True, capture_output=True, timeout=15).stdout
    actual = (repository / name).read_bytes()
    if actual.replace(b'\r\n', b'\n') != reference.replace(b'\r\n', b'\n'):
        raise ValueError('Conformal criterion source differs from the pinned Git commit.')
    return {'git_head': revision, 'script': 'third_party/ConU/' + name,
            'script_lf_sha256': io.digest(reference.replace(b'\r\n', b'\n')),
            'git_blob_sha1': hashlib.sha1(b'blob ' + str(len(reference)).encode('ascii') + b'\0' + reference).hexdigest()}


def load_scores(project):
    records, questions, split, hashes, upstream = scoring.validate_inputs(project)
    root = project / 'cache/a2_conu_pilot_v2/similarity'
    plan = io.read_json(root / 'plan.json')
    manifest = io.read_json(root / 'manifest.json')
    plan_hash = scoring.file_hash(root / 'plan.json')
    if (plan.get('schema') != 'confqa.conu.a2_similarity_plan.v1'
            or plan.get('script_sha256') != scoring.file_hash(Path(scoring.__file__))
            or plan.get('input_sha256') != hashes or plan.get('upstream') != upstream
            or plan.get('questions') != [row['qid'] for row in records]
            or plan.get('canonical_gold') != {q['qid']: q['gold_value'] for q in questions}
            or plan.get('calibration_ids') != split['calibration_ids']
            or plan.get('test_ids') != split['test_ids']):
        raise ValueError('Similarity plan does not match the frozen input, scorer, or 25/25 split.')
    if (manifest.get('schema') != 'confqa.conu.a2_similarity_result.v1'
            or manifest.get('plan_sha256') != plan_hash
            or [manifest.get(key) for key in ['questions', 'responses', 'predicted_pairs',
                                            'dropped_questions', 'dropped_responses']] != [50, 250, 750, 0, 0]
            or scoring.file_hash(root / 'scores.jsonl') != manifest['outputs']['scores.jsonl']['sha256']):
        raise ValueError('Expected the complete, unchanged 50-question scoring output.')
    scores = [json.loads(line) for line in (root / 'scores.jsonl').read_text(encoding='utf-8').splitlines()]
    if len(scores) != 50:
        raise ValueError('Expected exactly 50 score records.')
    for index, (saved, record, question) in enumerate(zip(scores, records, questions)):
        name = f'questions/{index:04d}.json'
        if (scoring.file_hash(root / name) != manifest['checkpoint_files'][name]
                or saved != io.read_json(root / name)):
            raise ValueError('Similarity export differs from its saved question checkpoints.')
        scoring.validate_checkpoint(saved, record, question['gold_value'], plan_hash)
    provenance = criterion_source(project, upstream['git_head'])
    for name in ['plan.json', 'manifest.json', 'scores.jsonl']:
        relative = 'cache/a2_conu_pilot_v2/similarity/' + name
        hashes[relative] = scoring.file_hash(project / relative)
    return scores, split, hashes, provenance


def features(record, threshold):
    matrix = np.asarray(record['similarity_matrix'], dtype=float)
    truth = np.asarray(record['similarity_to_canonical_gold'], dtype=float)
    if (matrix.shape != (5, 5) or truth.shape != (5,) or not np.isfinite(matrix).all()
            or not np.isfinite(truth).all() or (matrix < 0).any() or (matrix > 1).any()
            or (truth < 0).any() or (truth > 1).any()):
        raise ValueError('Invalid similarity dimensions or values.')
    frequency = np.array([np.sum(row >= threshold) / len(row) for row in matrix])
    probability = frequency / np.sum(frequency)
    best = record['similarity_to_canonical_gold'].index(max(record['similarity_to_canonical_gold']))
    acceptable = (truth >= threshold).tolist()
    return {'qid': record['qid'], 'question': record['question'], 'role': record['role'],
            'canonical_gold': record['canonical_gold'], 'samples': list(record['samples']),
            'gold_similarity': truth.tolist(), 'acceptable_samples': acceptable,
            'has_acceptable_sample': any(acceptable),
            'frequency': frequency.tolist(), 'normalized_frequency': probability.tolist(),
            'sample_nonconformity': (1 - probability).tolist(), 'most_reliable_index': best,
            'reference_nonconformity': float(1 - probability[best])}


def calibrate(calibration, alpha):
    # This is the active score in the pinned implementation. Its computed entropy
    # and semantic-diversity quantities are not added to this score.
    eligible = [row for row in calibration if row['has_acceptable_sample']]
    scores = [row['reference_nonconformity'] for row in eligible]
    result = {'alpha': alpha, 'target_coverage': 1 - alpha,
              'calibration_ids_used': [row['qid'] for row in eligible],
              'calibration_nonconformity': scores, 'n_calibration_used': len(scores),
              'quantile_method': 'upstream np.quantile(method=higher)',
              'q_level': None, 'q_hat': None, 'q_hat_is_infinite': False}
    if not scores:
        return {**result, 'status': 'no_applicable_calibration_questions'}
    q_level = float(np.ceil((len(scores) + 1) * (1 - alpha)) / len(scores))
    result['q_level'] = q_level
    if q_level > 1:
        # Upstream would raise here. Explicitly use the conservative full-set
        # extension, record it, and never silently clip q_level into [0,1].
        return {**result, 'status': 'conservative_infinite_threshold_small_calibration',
                'q_hat_is_infinite': True,
                'note': 'q_level exceeds 1; upstream quantile is undefined. +infinity selects all five slots.'}
    return {**result, 'status': 'calibrated', 'q_hat': float(np.quantile(scores, q_level, method='higher'))}


def answer_set(row, calibration):
    if calibration['status'] == 'no_applicable_calibration_questions':
        return None
    q_hat = math.inf if calibration['q_hat_is_infinite'] else calibration['q_hat']
    indices = [i for i, score in enumerate(row['sample_nonconformity']) if score <= q_hat]
    texts = [row['samples'][i] for i in indices]
    return {'indices': indices, 'answers': texts, 'set_size_slots': len(indices),
            'set_size_unique_text': len(set(texts)),
            'covered': any(row['acceptable_samples'][i] for i in indices)}


def metrics(rows, sets):
    values = [sets[row['qid']] for row in rows]
    if not values or any(value is None for value in values):
        return {'n_test': len(rows), 'covered_count': None, 'coverage': None,
                'miscoverage': None, 'average_set_size_slots': None,
                'average_set_size_unique_text': None, 'empty_set_count': None}
    covered = sum(value['covered'] for value in values)
    return {'n_test': len(rows), 'covered_count': covered, 'coverage': covered / len(values),
            'miscoverage': 1 - covered / len(values),
            'average_set_size_slots': sum(value['set_size_slots'] for value in values) / len(values),
            'average_set_size_unique_text': sum(value['set_size_unique_text'] for value in values) / len(values),
            'empty_set_count': sum(value['set_size_slots'] == 0 for value in values)}


def evaluate(scores, split, threshold, alphas):
    rows = [features(record, threshold) for record in scores]
    by_id = {row['qid']: row for row in rows}
    if len(by_id) != len(rows) or set(by_id) != set(split['calibration_ids']) | set(split['test_ids']):
        raise ValueError('Scores and split IDs differ or contain duplicates.')
    if set(split['calibration_ids']) & set(split['test_ids']):
        raise ValueError('Calibration and test sets must be disjoint.')
    calibration = [by_id[qid] for qid in split['calibration_ids']]
    test = [by_id[qid] for qid in split['test_ids']]
    if any(row['role'] != 'calibration' for row in calibration) or any(row['role'] != 'test' for row in test):
        raise ValueError('Score roles disagree with the frozen split.')
    eligible_test = [row for row in test if row['has_acceptable_sample']]
    cases = []
    for alpha in alphas:
        quantile = calibrate(calibration, alpha)
        sets = {row['qid']: answer_set(row, quantile) for row in rows}
        key = format(alpha, '.10g')
        for row in rows:
            row.setdefault('prediction_sets', {})[key] = sets[row['qid']]
        cases.append({'calibration': quantile,
                      'filtered_test': metrics(eligible_test, sets),
                      'all_fixed_test_same_threshold': metrics(test, sets)})
    n_eligible = sum(row['has_acceptable_sample'] for row in rows)
    summary = {'schema': 'confqa.conu.a2_conformal_result.v1', 'scope': '50-question pipeline pilot',
               'correctness_threshold': threshold, 'alphas': alphas,
               'n_total': len(rows), 'n_applied': n_eligible, 'n_excluded': len(rows) - n_eligible,
               'excluded_fraction': (len(rows) - n_eligible) / len(rows),
               'fixed_calibration_count': len(calibration), 'fixed_test_count': len(test),
               'calibration_eligible_count': sum(row['has_acceptable_sample'] for row in calibration),
               'test_eligible_count': len(eligible_test),
               'excluded_calibration_ids': [row['qid'] for row in calibration if not row['has_acceptable_sample']],
               'excluded_test_ids': [row['qid'] for row in test if not row['has_acceptable_sample']],
               'all_test_candidate_oracle_coverage': len(eligible_test) / len(test) if test else None,
               'cases': cases,
               'notes': [
                   'Use canonical-gold CrossEncoder similarity >= the explicit correctness threshold.',
                   'The same threshold is used for pairwise similarity frequency, as in upstream.',
                   'Retain the original 25/25 split; apply the upstream acceptable-answer condition within each partition.',
                   'Upstream filters before randomly splitting. This fixed-partition pilot is an explicit adaptation.',
                   'Quantile is the exact upstream higher-quantile rule where its q_level <= 1.',
                   'Primary nonconformity is 1 - normalized frequency of the max-gold-similarity sample; first tie wins.',
                   'All-fixed-test metrics reuse the filtered-calibration threshold; this is an audit view, not a separately unfiltered calibration.',
                   'Primary set size counts sample indices, including duplicate text, as in upstream; unique-text size is supplementary.',
                   'Filtered coverage is conditional. The small pilot does not establish population coverage or complete A3/A4/A5.',
               ]}
    return rows, summary


def main(project=None, threshold=0.6, alphas=None):
    project = project or Path(__file__).resolve().parent
    alphas = [0.1, 0.2] if alphas is None else list(alphas)
    if not 0 < threshold <= 1 or not alphas or len(set(alphas)) != len(alphas) or any(not 0 < alpha < 1 for alpha in alphas):
        raise ValueError('Use a threshold in (0,1] and distinct alpha values in (0,1).')
    scores, split, input_hashes, upstream = load_scores(project)
    rows, summary = evaluate(scores, split, threshold, alphas)
    root = project / 'cache/a2_conu_pilot_v2/conformal'
    plan = {'schema': 'confqa.conu.a2_conformal_plan.v1', 'script_sha256': scoring.file_hash(Path(__file__)),
            'input_sha256': input_hashes, 'upstream': upstream, 'correctness_threshold': threshold,
            'alphas': alphas, 'split': split, 'numpy_version': importlib.metadata.version('numpy'),
            'device': 'cpu', 'new_generation_requests': 0, 'new_model_predictions': 0,
            'adaptations': summary['notes']}
    products = {'plan.json': io.encode(plan), 'summary.json': io.encode(summary),
                'questions.jsonl': scoring.jsonl(rows)}
    manifest = {'schema': 'confqa.conu.a2_conformal_manifest.v1',
                'outputs': {name: {'sha256': io.digest(data)} for name, data in products.items()},
                'questions_retained': len(rows), 'responses_retained': sum(len(row['samples']) for row in rows),
                'new_generation_requests': 0, 'new_model_predictions': 0}
    products['manifest.json'] = io.encode(manifest)
    for name, content in products.items():
        target = root / name
        if target.is_symlink() or (target.exists() and target.read_bytes() != content):
            raise ValueError(f'Refusing to replace different conformal output: {target}')
    if any(scoring.file_hash(project / name) != expected for name, expected in input_hashes.items()):
        raise ValueError('Input changed during evaluation; no output was written.')
    for name, content in products.items():
        io.atomic_write(root / name, content, immutable=True)
    print('A2 CONFORMAL DONE', flush=True)
    print(f"Total: {summary['n_total']}; Applied: {summary['n_applied']}; Excluded: {summary['n_excluded']}", flush=True)
    print(f"Fixed split: 25 calibration / 25 test; eligible: {summary['calibration_eligible_count']} calibration / {summary['test_eligible_count']} test", flush=True)
    for case in summary['cases']:
        quantile = case['calibration']
        threshold_text = '+infinity' if quantile['q_hat_is_infinite'] else str(quantile['q_hat'])
        print(f"alpha={quantile['alpha']}; target={quantile['target_coverage']}; q_hat={threshold_text}; status={quantile['status']}", flush=True)
        for name in ['filtered_test', 'all_fixed_test_same_threshold']:
            result = case[name]
            print(f"  {name}: n={result['n_test']}; coverage={result['coverage']}; avg_set_size={result['average_set_size_slots']}", flush=True)
    print('Output:', root / 'summary.json', flush=True)
    print('CPU only; all 50 questions and 250 answer slots retained. No model loaded or queried.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--correctness-threshold', type=float, default=0.6)
    parser.add_argument('--alphas', type=float, nargs='+', default=[0.1, 0.2])
    options = parser.parse_args()
    # Preserve the traceback if anything fails; do not hide the actionable line.
    main(threshold=options.correctness_threshold, alphas=options.alphas)
