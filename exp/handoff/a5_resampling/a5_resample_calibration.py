"""Measure calibration-subset sensitivity from score-only ConU exports."""

import argparse
import hashlib
import json
import math
import random
from bisect import bisect_right
from collections import Counter
from pathlib import Path
from statistics import quantiles


def load_inputs(scores_path, cutoffs_path):
    export = json.loads(scores_path.read_bytes())
    cutoffs = json.loads(cutoffs_path.read_bytes())
    if set(export) != {'calibration_ids', 'test_ids', 'scores'}:
        raise ValueError('Unexpected score-export fields.')
    cal_ids, test_ids = export['calibration_ids'], export['test_ids']
    if len(cal_ids) != 250 or len(test_ids) != 250 or len(set(cal_ids + test_ids)) != 500:
        raise ValueError('Expected distinct frozen calibration and test pools of 250 questions each.')
    rows = export['scores']
    if any(set(row) != {'qid', 'r', 'ok'} or type(row['ok']) is not bool
           or type(row['r']) not in (int, float) or not 0 <= row['r'] <= 1 for row in rows):
        raise ValueError('Expected one scalar reference score and eligibility flag per question.')
    scores = {row['qid']: row for row in rows}
    if len(rows) != 500 or set(scores) != set(cal_ids + test_ids) or set(cutoffs) != set(test_ids):
        raise ValueError('Score rows or coverage cutoffs do not match the frozen IDs.')
    for qid in test_ids:
        cutoff = cutoffs[qid]
        if scores[qid]['ok'] != (cutoff is not None) or (
                cutoff is not None and (type(cutoff) not in (float, int)
                                        or not 0 <= cutoff <= scores[qid]['r'])):
            raise ValueError(f'Invalid minimum acceptable nonconformity for {qid}.')
    return [scores[qid]['r'] for qid in cal_ids], [cutoffs[qid] for qid in test_ids]


def conu_threshold(sorted_scores, alpha):
    """Match the fixed upstream np.quantile(..., method='higher') rule."""
    n = len(sorted_scores)
    level = math.ceil((n + 1) * (1 - alpha)) / n
    if level > 1:
        raise ValueError('Calibration subset is too small for this alpha.')
    return sorted_scores[math.ceil((n - 1) * level)]


def describe(values):
    low, high = min(values), max(values)
    if low == high:
        return {'p05': low, 'p95': high, 'min': low, 'max': high}
    bounds = quantiles(values, n=20, method='inclusive')
    return {'p05': bounds[0], 'p95': bounds[-1], 'min': low, 'max': high}


def run(scores, cutoffs, seed, draws):
    if draws < 2:
        raise ValueError('At least two draws are required.')
    test_thresholds = sorted(cutoff for cutoff in cutoffs if cutoff is not None)
    rng = random.Random(seed)
    results = []
    alphas = (0.1, 0.2)
    for n_cal in (100, 150, 250):
        observations = {alpha: [] for alpha in alphas}
        subsets = set()
        for _ in range(draws):
            indices = rng.sample(range(len(scores)), n_cal)
            subsets.add(frozenset(indices))
            subset = sorted(scores[i] for i in indices)
            for alpha in alphas:
                q_hat = conu_threshold(subset, alpha)
                covered = bisect_right(test_thresholds, q_hat)
                observations[alpha].append((q_hat, covered))
        for alpha, rows in observations.items():
            results.append({
                'n_calibration': n_cal, 'alpha': alpha, 'draws': draws,
                'unique_subsets': len(subsets),
                'q_hat': describe([q for q, _ in rows]),
                'coverage': describe([covered / len(cutoffs) for _, covered in rows]),
                'joint_counts': [
                    {'q_hat': q, 'covered_count': covered, 'count': count}
                    for (q, covered), count in sorted(Counter(rows).items())
                ],
            })
    return {
        'schema': 'confqa.conu.calibration_subset_sensitivity.v1',
        'seed': seed, 'draws_per_size': draws, 'calibration_pool_size': len(scores),
        'test_size': len(cutoffs), 'test_with_acceptable_candidate': len(test_thresholds),
        'atom_0_95_in_calibration_pool': scores.count(0.95),
        'sampling': 'Uniform subsets without replacement within each draw; same draw for both alphas.',
        'quantile_rule': 'ceil((n+1)*(1-alpha))/n with higher interpolation, as in A5.',
        'interval_rule': 'Empirical 5th and 95th percentiles with linear interpolation.',
        'scope': 'Fixed calibration pool, fixed test questions, fixed cached candidates and scores.',
        'results': results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scores', type=Path, default=Path('a3_scores_export.json'))
    parser.add_argument('--test-cutoffs', type=Path, default=Path('test_coverage_cutoffs.json'))
    parser.add_argument('--out', type=Path, default=Path('a5_calibration_resampling.json'))
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--draws', type=int, default=1000)
    args = parser.parse_args()
    scores, cutoffs = load_inputs(args.scores, args.test_cutoffs)
    summary = run(scores, cutoffs, args.seed, args.draws)
    summary['input_sha256'] = {
        'scores': hashlib.sha256(args.scores.read_bytes()).hexdigest(),
        'test_cutoffs': hashlib.sha256(args.test_cutoffs.read_bytes()).hexdigest(),
    }
    body = json.dumps(summary, indent=2, allow_nan=False) + '\n'
    with args.out.open('x', encoding='utf-8', newline='\n') as handle:
        handle.write(body)
    print(args.out)


if __name__ == '__main__':
    main()
