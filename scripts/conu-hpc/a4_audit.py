#!/usr/bin/env python3
"""Compare independently calibrated ConU variants using the frozen A3 scores on CPU."""
import csv
import io
import subprocess
import sys
import tempfile
from pathlib import Path

import a3_run as a3


CRITERION = 'conformal_uncertainty_criterion.py'
PATCH_PATH = 'patches/conu-no-filter.patch'
OUTPUT_DIR = 'cache/a4_filter_audit'
PATCH = r"""--- a/conformal_uncertainty_criterion.py
+++ b/conformal_uncertainty_criterion.py
@@ -1,17 +1,10 @@
 import argparse
-import pathlib
 import pickle
-import tqdm
 import os
 import random
 import json
 
-import accelerate
-import datasets
-from transformers import AutoModelForCausalLM, AutoTokenizer
-
 import numpy as np
-import torch
 
 
 parser = argparse.ArgumentParser()
@@ -42,6 +35,11 @@
 parser.add_argument('--correctness-threshold', type=float, default=0.7, help='for correctness evaluation')
 parser.add_argument('--alpha', type=float, default=0.2, help='risk level')
 # ----------------------------------------------------------------------------------------------------------------------
+parser.add_argument('--no-filter', action='store_true',
+                    help='Keep questions with no acceptable sampled answer')
+parser.add_argument('--a3-scores', help='Read A3 similarity scores JSONL instead of upstream pickle files')
+parser.add_argument('--fixed-split', help='Use frozen calibration/test IDs from this JSON file')
+parser.add_argument('--result-json', help='Save counts, threshold, and metrics to this JSON file')
 args = parser.parse_args()
 # run_name for saving experimental record
 model_name = args.generate_model.split('\\')[-1] if '\\' in args.generate_model else args.generate_model
@@ -69,41 +67,54 @@
 random.seed(seed_value)
 # 3. Set `numpy` pseudo-random generator at a fixed value
 np.random.seed(seed_value)
-# 4. Fix torch random seed
-torch.manual_seed(seed_value)
 # cache path for hf_datasets
 os.environ["HF_DATASETS_CACHE"] = args.cache_dir
-# set cuda device 0,1
-os.environ["CUDA_VISIBLE_DEVICES"] = '0,1'
-# ----------------------------------------------------------------------------------------------------------------------
-# load generation
-with open(f'{run_name}/cleaned_generations.pkl', 'rb') as record_file:
-    generations = pickle.load(record_file)
-# load similarity scores
-with open(f'{run_name}/similarity_scores.pkl', 'rb') as record_file:
-    similarity_scores = pickle.load(record_file)
-
-similarity_dict, similarity_for_correctness = similarity_scores
+# ----------------------------------------------------------------------------------------------------------------------
+if args.a3_scores:
+    with open(args.a3_scores, encoding='utf-8') as handle:
+        records = [json.loads(line) for line in handle]
+    generations = [{'id': record['qid']} for record in records]
+    similarity_dict = {record['qid']: dict(enumerate(record['similarity_matrix']))
+                       for record in records}
+    similarity_for_correctness = {record['qid']: record['similarity_to_canonical_gold']
+                                  for record in records}
+else:
+    with open(f'{run_name}/cleaned_generations.pkl', 'rb') as record_file:
+        generations = pickle.load(record_file)
+    with open(f'{run_name}/similarity_scores.pkl', 'rb') as record_file:
+        similarity_dict, similarity_for_correctness = pickle.load(record_file)
 # ----------------------------------------------------------------------------------------------------------------------
 # assumption: at least one acceptable generation
 applied_generations = []
 for generation in generations:
     id = generation['id']
     similarity_for_correctness_list = similarity_for_correctness[id]
-    if max(similarity_for_correctness_list) >= args.correctness_threshold:
+    if args.no_filter or max(similarity_for_correctness_list) >= args.correctness_threshold:
         applied_generations.append(generation)
 
 total_num = len(applied_generations)
-num_cal = int(total_num * args.split_ratio)
-calibration_set = random.sample(applied_generations, num_cal)
-test_set = [generation for generation in applied_generations if generation not in calibration_set]
+if args.fixed_split:
+    with open(args.fixed_split, encoding='utf-8') as handle:
+        split = json.load(handle)
+    calibration_ids, test_ids = split['calibration_ids'], split['test_ids']
+    all_ids = calibration_ids + test_ids
+    source_ids = [generation['id'] for generation in generations]
+    if len(all_ids) != len(set(all_ids)) or sorted(all_ids) != sorted(source_ids):
+        raise ValueError('Frozen split must partition all input question IDs.')
+    applied_by_id = {generation['id']: generation for generation in applied_generations}
+    calibration_set = [applied_by_id[qid] for qid in calibration_ids if qid in applied_by_id]
+    test_set = [applied_by_id[qid] for qid in test_ids if qid in applied_by_id]
+else:
+    num_cal = int(total_num * args.split_ratio)
+    calibration_set = random.sample(applied_generations, num_cal)
+    test_set = [generation for generation in applied_generations if generation not in calibration_set]
 print('Applied num: ', total_num)
 print('Calibration num: ', len(calibration_set))
 print('Test num: ', len(test_set))
 # ----------------------------------------------------------------------------------------------------------------------
 # nonconformity scores in calibration set
 nonconformity_scores = []
-for cal_data in tqdm.tqdm(calibration_set):
+for cal_data in calibration_set:
     cal_id = cal_data['id']
     # for NS
     sampled_similarity_dict = similarity_dict[cal_id]
@@ -140,7 +151,7 @@
 miscoverage_num = 0
 total_set_size = 0
 total_confidence_weighted_ss = 0
-for test_data in tqdm.tqdm(test_set):
+for test_data in test_set:
     test_id = test_data['id']
     sampled_similarity_dict = similarity_dict[test_id]
     sampled_correctness_similarity_list = np.array(similarity_for_correctness[test_id])
@@ -171,5 +182,26 @@
 miscoverage_rate = miscoverage_num / len(test_set)
 print('EMR: ', miscoverage_rate)
 print('APSS: ', total_set_size / len(test_set))
+if args.result_json:
+    covered_count = len(test_set) - miscoverage_num
+    result = {
+        'alpha': args.alpha,
+        'no_filter': args.no_filter,
+        'n_total': len(generations),
+        'n_used': total_num,
+        'n_dropped': len(generations) - total_num,
+        'dropped_fraction': (len(generations) - total_num) / len(generations),
+        'calibration_ids': [row['id'] for row in calibration_set],
+        'test_ids': [row['id'] for row in test_set],
+        'n_calibration': len(calibration_set),
+        'n_test': len(test_set),
+        'q_level': float(q_level),
+        'q_hat': float(q_hat),
+        'covered_count': covered_count,
+        'coverage': covered_count / len(test_set),
+        'average_set_size_slots': total_set_size / len(test_set),
+    }
+    with open(args.result_json, 'w', encoding='utf-8') as handle:
+        json.dump(result, handle, allow_nan=False)
 
 
"""


def load_a3(project):
    root = project / a3.CACHE
    read = a3.io.read_json
    files = ['plan.json', 'split.json', 'similarity/plan.json', 'similarity/scores.jsonl',
             'similarity/manifest.json', 'conformal/summary.json', 'conformal/manifest.json']
    hashes = {name: a3.scoring.file_hash(root / name) for name in files}
    plan = read(root / 'plan.json')
    split = read(root / 'split.json')
    processing = read(root / 'similarity/plan.json')
    similarity = read(root / 'similarity/manifest.json')
    summary = read(root / 'conformal/summary.json')
    conformal = read(root / 'conformal/manifest.json')
    if (split != plan['split']
            or processing['sampling_plan_sha256'] != hashes['plan.json']
            or similarity['plan_sha256'] != hashes['similarity/plan.json']
            or summary['processing_plan_sha256'] != hashes['similarity/plan.json']
            or similarity['scores_sha256'] != hashes['similarity/scores.jsonl']
            or conformal['outputs']['summary.json'] != hashes['conformal/summary.json']):
        raise ValueError('A3 score, summary, or fixed split differs from its saved manifest.')
    if (similarity['questions'], similarity['responses'], similarity['predicted_pairs']) != (500, 10000, 105000):
        raise ValueError('Expected completed A3 similarity scores for 500 questions and 10,000 answers.')
    if (processing['correctness_threshold'], processing['alphas']) != (.6, [.1, .2]):
        raise ValueError('Unexpected A3 correctness threshold or alpha settings.')
    scores = a3.post.read_jsonl(root / 'similarity/scores.jsonl')
    cal_ids, test_ids = split['calibration_ids'], split['test_ids']
    qids = [row['qid'] for row in scores]
    if (qids != split['generation_order'] or len(qids) != 500
            or len(cal_ids) != 250 or len(test_ids) != 250
            or len(set(cal_ids + test_ids)) != 500 or set(qids) != set(cal_ids + test_ids)):
        raise ValueError('A3 scores do not match 500 distinct IDs in the frozen 250/250 split.')
    eligible = {row['qid'] for row in scores if max(row['similarity_to_canonical_gold']) >= .6}
    return root, split, eligible, summary, hashes, processing['criterion_source']


def run_command(command, directory):
    process = subprocess.run(command, cwd=directory, capture_output=True, timeout=60)
    if process.returncode:
        detail = (process.stderr or process.stdout).decode('utf-8', errors='replace').strip()
        raise ValueError(detail or f'{command[0]} exited with code {process.returncode}')


def evaluate(project, root, split, eligible, baseline, source):
    pinned = a3.conformal.criterion_source(project, a3.post.cleaning.CONU_HEAD)
    if pinned != source:
        raise ValueError('The ConU criterion differs from the source recorded by A3.')
    upstream = (project / source['script']).read_bytes().replace(b'\r\n', b'\n')
    results = []
    with tempfile.TemporaryDirectory(prefix='conu-a4-') as temporary:
        work = Path(temporary)
        (work / CRITERION).write_bytes(upstream)
        (work / 'no-filter.patch').write_bytes(PATCH.encode('utf-8'))
        run_command(['git', 'apply', 'no-filter.patch'], work)
        for case in baseline['cases']:
            alpha = case['calibration']['alpha']
            for no_filter in (False, True):
                command = [sys.executable, CRITERION, '--a3-scores', str(root / 'similarity/scores.jsonl'),
                           '--fixed-split', str(root / 'split.json'), '--correctness-threshold', '0.6',
                           '--alpha', str(alpha), '--result-json', 'result.json']
                if no_filter:
                    command.append('--no-filter')
                run_command(command, work)
                result = a3.io.read_json(work / 'result.json')
                for role in ('calibration', 'test'):
                    key = f'{role}_ids'
                    expected = [qid for qid in split[key] if no_filter or qid in eligible]
                    if result[key] != expected:
                        raise ValueError(f'Patched ConU used unexpected {role} IDs.')
                if not no_filter:
                    reference = case['filtered_test']
                    metrics = ['n_test', 'covered_count', 'coverage', 'average_set_size_slots']
                    if (result['q_hat'] != case['calibration']['q_hat']
                            or result['q_level'] != case['calibration']['q_level']
                            or any(result[name] != reference[name] for name in metrics)):
                        raise ValueError(f'Filtered run did not reproduce A3 at alpha={alpha}.')
                results.append(result)
    return results


def reports(results, split, eligible, baseline, hashes, source):
    counts = {'total': 500, 'eligible': len(eligible), 'excluded': 500 - len(eligible),
              'excluded_fraction': (500 - len(eligible)) / 500}
    excluded = {role: [qid for qid in split[f'{role}_ids'] if qid not in eligible]
                for role in ('calibration', 'test')}
    summary = {
        'schema': 'confqa.conu.a4_filter_audit.v1',
        'correctness_threshold': .6,
        'partition_policy': 'fixed A3 calibration/test membership in both modes',
        'set_size_unit': 'response slots including duplicate text',
        'counts': counts,
        'excluded_ids': excluded,
        'results': results,
        'all_fixed_test_with_filtered_threshold': [
            {'alpha': case['calibration']['alpha'], 'q_hat': case['calibration']['q_hat'],
             **case['all_fixed_test_same_threshold']} for case in baseline['cases']],
        'all_test_candidate_oracle_coverage': (250 - len(excluded['test'])) / 250,
        'a3_input_sha256': hashes,
        'upstream': {**source, 'filter_lines': [88, 94], 'first_split_line': 97},
        'patch': PATCH_PATH,
        'patch_sha256': a3.io.digest(PATCH.encode('utf-8')),
        'runner_sha256': a3.scoring.file_hash(Path(__file__)),
    }
    csv_file = io.StringIO(newline='')
    columns = ['alpha', 'no_filter', 'n_total', 'n_used', 'n_dropped', 'dropped_fraction',
               'n_calibration', 'n_test', 'q_level', 'q_hat', 'covered_count', 'coverage',
               'average_set_size_slots']
    writer = csv.DictWriter(csv_file, fieldnames=columns, extrasaction='ignore')
    writer.writeheader()
    writer.writerows(results)
    markdown = [
        '# A4 ConU 过滤审计', '',
        f"A3 的 500 题中有 {counts['excluded']} 题（{counts['excluded_fraction']:.1%}）"
        f"的 20 条候选均未达到可接受标准。校准集 {len(excluded['calibration'])} 题，"
        f"测试集 {len(excluded['test'])} 题。", '',
        '| α | 口径 | 原始题数 | 纳入 | 排除 | 校准分母 | 测试分母 | q̂ | 覆盖 | 平均集合大小 |',
        '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|',
    ]
    for row in results:
        mode = '不过滤' if row['no_filter'] else '过滤'
        markdown.append(
            f"| {row['alpha']} | {mode} | {row['n_total']} | {row['n_used']} | "
            f"{row['n_dropped']} ({row['dropped_fraction']:.1%}) | {row['n_calibration']} | {row['n_test']} | "
            f"{row['q_hat']:.6g} | {row['covered_count']}/{row['n_test']} ({row['coverage']:.2%}) | "
            f"{row['average_set_size_slots']:.3f} |")
    markdown += [
        '', '原版 ConU 在第 88–94 行过滤，第 97 行起划分。此对照沿用 A3 冻结的题目归属，'
        '在原有划分内分别过滤，两个口径各自计算 q̂。',
        '不过滤版对每道校准题沿用原版的最高金标准相似度候选，包含最高分低于 0.6 的题。',
        '覆盖指预测集合至少含一个与金标准相似度 ≥0.6 的候选。集合大小按回答位置计数，包含重复文本。',
        f"完整测试集的候选覆盖上限为 {250 - len(excluded['test'])}/250 "
        f"（{summary['all_test_candidate_oracle_coverage']:.2%}）。", '',
    ]
    return {'summary.json': a3.io.encode(summary), 'metrics.csv': csv_file.getvalue().encode('utf-8-sig'),
            'metrics.md': '\n'.join(markdown).encode('utf-8')}


def main(project=None):
    project = Path(project or Path(__file__).resolve().parent).resolve()
    root, split, eligible, baseline, hashes, source = load_a3(project)
    results = evaluate(project, root, split, eligible, baseline, source)
    products = reports(results, split, eligible, baseline, hashes, source)
    a3.post.write_products(project, {PATCH_PATH: PATCH.encode('utf-8'),
                                   **{f'{OUTPUT_DIR}/{name}': data for name, data in products.items()}})
    print(f'A4 DONE: 500 questions; {500 - len(eligible)} without an acceptable sampled answer.')
    for row in results:
        mode = 'unfiltered' if row['no_filter'] else 'filtered'
        print(f"alpha={row['alpha']} {mode} n_cal={row['n_calibration']} q_hat={row['q_hat']:.6g} "
              f"coverage={row['covered_count']}/{row['n_test']} ({row['coverage']:.2%}) "
              f"avg_set_size={row['average_set_size_slots']:.3f}")
    print('Report:', project / OUTPUT_DIR / 'metrics.md')
    print('Patch:', project / PATCH_PATH)


if __name__ == '__main__':
    try:
        main()
    except (KeyError, OSError, ValueError, subprocess.SubprocessError) as error:
        sys.exit(f'A4 ERROR: {error}')
