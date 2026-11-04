# Artifact schemas

Every file that crosses a person boundary is defined here. **Change this file
before changing code.** Fields are append-only: never rename or repurpose an
existing key, add a new one instead.

All paths are relative to the repository root. `cache/` is git-ignored and
regenerable; `exp/results/` is tracked and is the only source of numbers for
the report.

---

## 1. ConU pipeline

### `cache/conu_generations.jsonl` — written once by `01_generate`

```json
{
  "qid": "triviaqa-dev-0001",
  "question": "Who wrote the novel ...?",
  "gold": ["Doris Lessing"],
  "samples": ["Doris Lessing", "Lessing", "..."],
  "model": "TODO",
  "decode": {"temperature": 1.0, "top_p": 0.9, "max_new_tokens": 32},
  "seed": 0
}
```

`samples` has length `num_samples` for every record, including duplicates.

### `cache/conu_scores.jsonl` — written by `02_similarity`

```json
{
  "qid": "triviaqa-dev-0001",
  "scores": [0.91, 0.44, 0.87],
  "sim_to_gold": [0.88, 0.21, 0.79],
  "is_correct": [true, false, true]
}
```

- `scores[i]`: ConU uncertainty score for sample `i` (repo definition).
- `sim_to_gold[i]`: semantic similarity to the gold answer.
- `is_correct[i]`: `sim_to_gold[i] >= correctness_threshold`. This is the
  only place the threshold is applied, so the audit can re-derive it later.

### `exp/results/conu__a<alpha>__calib<ratio>.json`

```json
{
  "pipeline": "conu",
  "config": "configs/base.yaml",
  "alpha": 0.1,
  "calib_ratio": 0.5,
  "threshold": 0.62,
  "n_total": 500,
  "n_used": 412,
  "n_dropped_unanswerable": 88,
  "coverage": 0.907,
  "coverage_ci": [0.872, 0.938],
  "avg_set_size": 3.42,
  "seed": 0
}
```

`n_dropped_unanswerable` is the filtering audit: examples removed because no
sample was correct. **Report it next to every coverage number.**

---

## 2. Conformal factuality pipeline

### `cache/factuality_claims.jsonl` — written once by `01_claims`

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
prompt hash in the result json, and report human agreement on a sample.

### `exp/results/fact__a<alpha>__calib<ratio>.json`

```json
{
  "pipeline": "factuality",
  "alpha": 0.1,
  "calib_ratio": 0.5,
  "threshold": 0.55,
  "n_responses": 183,
  "all_correct_nonempty": 0.91,
  "retention": 0.72,
  "empty_rate": 0.03,
  "judge_agreement": 0.88
}
```

---

## 3. Extension (Part 4)

### `cache/ext_responses.jsonl`

```json
{"pid": "ext-0001", "prompt": "...", "responses": ["...", "...", "...", "...", "..."]}
```

### `cache/ext_clusters.jsonl`

```json
{
  "pid": "ext-0001",
  "claims": [
    {"rid": 0, "cid": 3, "text": "...", "cluster_id": 7, "support": 0.8, "score": 0.8}
  ]
}
```

- `cluster_id`: index of the semantic cluster the claim was merged into.
- `support`: fraction of responses containing an equivalent claim.
- `score`: the value fed into the filtering threshold (may equal support).

### `exp/results/ext__a<alpha>__calib<ratio>.json`

Same keys as the factuality result plus `"baseline_result"` pointing at the
file it is compared against (same prompts, same sampling budget).

---

## Naming rule

`<pipeline>__a<alpha>__calib<ratio>.json`, e.g.
`conu__a0.1__calib0.5.json`. One file per run, never overwritten by hand.
