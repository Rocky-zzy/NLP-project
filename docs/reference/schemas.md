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
  "n_responses": 50,
  "all_correct_nonempty": 0.91,
  "retention": 0.72,
  "empty_rate": 0.03,
  "judge_agreement": 0.88
}
```

---

## 4. Extension (Part 4)

### `cache/ext_responses.jsonl`

```json
{"pid": "factscore-0001", "prompt": "...", "responses": ["...", "...", "...", "...", "..."]}
```

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
