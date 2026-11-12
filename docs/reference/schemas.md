# Artifact schemas

Every file that crosses a person boundary is defined here. **Change this file
before changing code.** Fields are append-only: never rename or repurpose an
existing key, add a new one instead.

All paths are relative to the repository root. `cache/` is git-ignored and
regenerable; `exp/results/` is tracked and is the only source of numbers for
the report.

---

## 0. Split files — `data/splits/<dataset>.json` (owner: C)

Built **once**, committed, never regenerated. Every reported number must name
the split file it used.

```json
{
  "schema_version": 1,
  "dataset": "factscore",
  "source": "third_party/conformal-factual-lm/data/factscore_annotations.jsonl",
  "source_sha256": "…",
  "seed": 0,
  "test_ratio": 0.5,
  "dev_ratio": 0.1,
  "n_total": 50,
  "ids_sha256": "…",
  "counts": {"test": 25, "dev": 5, "calib_pool": 20},
  "splits": {
    "test": ["factscore-0003", "…"],
    "dev": ["factscore-0011", "…"],
    "calib_pool": ["factscore-0000", "…"]
  }
}
```

Rules:

- `test` is never used for tuning of any kind.
- `dev` is only for choosing prompts, thresholds or prompts; never for the
  final numbers.
- calibration size = `calib_frac` × |`calib_pool`|, with
  `calib_frac ∈ {0.5, 0.75, 1.0}`. That is the "calibration-set size" factor
  from Part 3: `test` and `dev` stay fixed while only the calibration subset moves.
- `ids_sha256` is computed over the sorted id list, so it is stable
  regardless of file formatting.

Build it with:

```bash
python -m confqa.common.splits --dataset factscore \
    --annotations third_party/conformal-factual-lm/data/factscore_annotations.jsonl \
    --out data/splits/factscore.json
```

---

## 1. Result files — `exp/results/<pipeline>__a<alpha>__calib<frac>.json`

Always written by `confqa.common.results.run_result`; the provenance block is
not optional.

```json
{
  "schema_version": 1,
  "pipeline": "conu",
  "created_at": "2026-11-12T09:31:00+00:00",
  "elapsed_s": 12.4,
  "git": {"commit": "…", "dirty": false},
  "config": {"path": "configs/base.yaml", "sha256": "…"},
  "model": "Qwen2.5-14B-Instruct",
  "seed": 0,
  "alpha": 0.1,
  "calib_frac": 0.5,
  "reportable": true,
  "coverage": 0.907,
  "avg_set_size": 3.42
}
```

- `reportable: false` means the working tree was dirty when the run finished.
  The number may be inspected, but it must not enter the report.
- `alpha` is the error rate, so the target level is 1 − α.
- Payload keys are merged at the top level and may not shadow the provenance keys.

---

## 2. ConU pipeline

### `cache/conu_generations.jsonl` — written once

```json
{
  "qid": "triviaqa-0001",
  "question": "Who wrote the novel ...?",
  "gold": ["Doris Lessing"],
  "samples": ["Doris Lessing", "Lessing", "..."],
  "model": "…",
  "decode": {"temperature": 1.0, "top_p": 0.9, "max_new_tokens": 32},
  "seed": 0
}
```

`samples` has length `num_samples` for every record, including duplicates.

### `cache/conu_scores.jsonl` — written by the similarity step

```json
{
  "qid": "triviaqa-0001",
  "scores": [0.91, 0.44, 0.87],
  "sim_to_gold": [0.88, 0.21, 0.79],
  "is_correct": [true, false, true]
}
```

- `scores[i]`: ConU uncertainty score for sample `i` (repo definition).
- `sim_to_gold[i]`: semantic similarity to the gold answer.
- `is_correct[i]`: `sim_to_gold[i] >= correctness_threshold`. This is the
  only place the threshold is applied, so the audit can re-derive it later.

### ConU result payload

```json
{
  "threshold": 0.62,
  "n_total": 500,
  "n_used": 412,
  "n_dropped_unanswerable": 88,
  "coverage": 0.907,
  "coverage_ci": [0.872, 0.938],
  "avg_set_size": 3.42
}
```

`n_dropped_unanswerable` is the filtering audit: examples removed because no
sample was correct. **Report it next to every coverage number.**

ConU A5 reuses the frozen TriviaQA A3 split with 250 calibration and 250 test
questions. The grid selects 100, 150, and 250 calibration questions, respectively
0.2, 0.3, and 0.5 of the full cohort (`calib_ratio_of_total`). `calib_frac` and
the filename still use the calibration pool as their denominator: 0.4, 0.6,
and 1.0. A5 records `n_calibration_used`, `n_test`, and `avg_set_size_ci`
alongside `coverage_ci`. Its primary metrics use all fixed test questions and
its `eligible_test` metrics use the same threshold on the answerable subset.

---

## 3. Conformal factuality pipeline

### `cache/factuality_claims.jsonl` — written once

```json
{
  "pid": "factscore-0001",
  "prompt": "Tell me a bio of ...",
  "response": "...",
  "claims": [{"cid": 0, "text": "...", "score": 0.87}]
}
```

### `cache/factuality_labels.jsonl` — human or judge

```json
{"pid": "factscore-0001", "cid": 0, "correct": true, "source": "human", "annotator": "A"}
```

`source` is `human` or `judge`. If `judge`, also record the judge model and
prompt hash in the result payload, and report human agreement on a sample.

### Factuality result payload

```json
{
  "threshold": 0.55,
  "confidence_method": "frequency",
  "required_correct_fraction": 1.0,
  "n_calibration": 10,
  "n_responses": 25,
  "n_claims": 201,
  "n_retained_claims": 103,
  "calibration_ids": ["factscore-0002", "…"],
  "calibration_ids_sha256": "…",
  "test_ids_sha256": "…",
  "scored_file": "third_party/…/factscore_subclaims_with_scores.jsonl",
  "scored_sha256": "…",
  "split_file": "data/splits/factscore.json",
  "split_sha256": "…",
  "upstream_commit": "6022b4c90c6580f524f123b0cb97bbb61ab621d1",
  "all_correct_nonempty": 0.91,
  "all_correct_nonempty_ci": [0.82, 1.0],
  "retention": 0.72,
  "retention_ci": [0.61, 0.81],
  "empty_rate": 0.03,
  "empty_rate_ci": [0.0, 0.08],
  "judge_agreement": 0.88
}
```

- `calibration_ids` is the exact fixed subset used to fit `threshold`.
- `scored_file` and `scored_sha256` pin the cached claim-score input.
- The three `*_ci` fields are percentile bootstrap intervals over test
  responses. Retention is recomputed from total retained and total original
  claims inside each bootstrap resample.
- `required_correct_fraction` is the paper's `a`; the course's all-retained-
  claims-correct metric uses `a = 1.0`.

---

## 4. Extension (Part 4)

### `cache/ext_responses.jsonl`

```json
{"pid": "factscore-0001", "prompt": "...", "responses": ["...", "...", "...", "...", "..."]}
```

### `cache/ext_claims.jsonl` — H3 claim splitting

```json
{
  "schema_version": 1,
  "pid": "factscore-0001",
  "response_id": 0,
  "model": "Qwen2.5-14B-Instruct",
  "response_sha256": "…",
  "breakdown_prompt_sha256": "…",
  "claims": [
    {"cid": 0, "text": "...", "gpt_score": 0.9}
  ]
}
```

- One row is written for every successfully parsed target response.
- `cid` is contiguous from zero within that response.
- `gpt_score` is optional because the frequency baseline does not require it.
- Split failures go to `cache/ext_h3_failures.jsonl`; they are never silently
  skipped.

### `cache/ext_judgments.jsonl` — H3 three-way judgments

```json
{
  "schema_version": 1,
  "pid": "factscore-0001",
  "target_response_id": 0,
  "comparison_response_ids": [0, 1, 2, 3, 4],
  "model": "Qwen2.5-14B-Instruct",
  "judged_by": "Qwen2.5-14B-Instruct",
  "judge_prompt_sha256": "…",
  "claims": [
    {
      "cid": 0,
      "text": "...",
      "judgments": [
        {"response_id": 0, "label": "support", "score": 1}
      ]
    }
  ]
}
```

- `score` is exactly `1` (support), `0` (unrelated), or `-1`
  (contradict).
- Every target claim must have one judgment for every configured comparison
  response.
- A judge parse failure invalidates that target row and is recorded in
  `cache/ext_h3_failures.jsonl`.

### `cache/ext_baseline_scores.jsonl`

```json
{
  "schema_version": 1,
  "pid": "factscore-0001",
  "target_response_id": 0,
  "prompt": "...",
  "claims": [
    {
      "cid": 0,
      "text": "...",
      "frequency_score": 5,
      "support_count": 5,
      "comparison_count": 5,
      "support_rate": 1.0
    }
  ]
}
```

- `frequency_score` is the sum of the three-way judgment scores.
- `support_rate` is the fraction of comparison responses marked support.
- `prompt` allows the score file to be joined with human labels and converted
  into the same `FactResponse` shape used by the cached-data pipeline.
- The same target/comparison policy must be used by the frequency baseline and
  semantic-clustering extension.

### `cache/ext_h3_failures.jsonl`

```json
{
  "schema_version": 1,
  "stage": "claim_split",
  "pid": "factscore-0001",
  "response_id": 0,
  "error_type": "ClaimParseError",
  "message": "...",
  "raw_output": "..."
}
```

`stage` is `claim_split` or `judge`. For a judge failure,
`target_response_id`, `cid`, and `comparison_response_id` identify the failed
pair. `raw_output` is retained in the ignored cache for debugging and audit.

### `cache/ext_clusters.jsonl`

```json
{
  "pid": "factscore-0001",
  "claims": [
    {"rid": 0, "cid": 3, "text": "...", "cluster_id": 7, "support": 0.8, "score": 0.8}
  ]
}
```

- `cluster_id`: index of the semantic cluster the claim was merged into.
- `support`: fraction of responses containing an equivalent claim.
- `score`: the value fed into the filtering threshold (may equal support).

### Extension result payload

Same keys as the factuality payload plus `"baseline_result"` naming the result
file it is compared against (same prompts, same sampling budget).

---

## Naming rule

`<pipeline>__a<alpha>__calib<frac>.json`, e.g. `conu__a0.1__calib0.5.json`.
One file per run, never overwritten by hand.
