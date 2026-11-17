# B2 — does the clustering threshold explain the contradiction rate?

Answer: **no**. Raising the similarity threshold breaks clusters apart and
destroys coverage long before it removes contradicted claims.

## Method

The three strict thresholds were run on a CPU-only workstation, not on the
cluster, using the cache recovered from the HPC on 2026-11-17:

```bash
cd NLP-project
for t in 0.75 0.85 0.90; do
  PYTHONPATH=src python -m confqa.extension.cluster \
    --claims cache/h3/ext_claims.jsonl \
    --baseline cache/h3/ext_baseline_scores.jsonl \
    --encoder cross-encoder/stsb-roberta-large \
    --device cpu --batch 64 --threshold "$t" \
    --out "cache/ext/clusters_t$t.jsonl"
done
```

`--device` was added for this (commit 405ccbc; it defaults to `cuda:0`, so the
cluster behaviour is unchanged). Before the runs, the CPU path was checked
against the committed clustering: one prompt, 9 target claims, 9/9 identical
support scores. 65,140 cross-response pairs per threshold, 11.8–20.6 pairs/s,
37 minutes per threshold, 1 h 50 m in total.

The `0.60` row is the committed `cache/ext/clusters.jsonl`, not a rerun.

## Result

Claims means the 550 target claims of response 0. *Real claims* excludes the
`not_claim` verdicts (sentences that are not factual assertions), which is the
population used in the Part 4 analysis.

| threshold | clusters | mean size | at support 1.0 | real claims at 1.0 | supported | contradicted | contradiction rate |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.60 | 227 | 2.42 | 355 | 304 | 66 (21.7%) | 50 | **16.4%** |
| 0.75 | 458 | 1.20 | 95 | 79 | 24 (30.4%) | 8 | 10.1% |
| 0.85 | 535 | 1.03 | 17 | 14 | 6 (42.9%) | 3 | 21.4% |
| 0.90 | 546 | 1.01 | 5 | 4 | 4 (100%) | 0 | 0.0% |

Coverage among the 452 real claims: 67% → 17% → 3% → 0.9%.

## Reading

1. **Coverage collapses first.** Going from 0.60 to 0.75 costs three quarters of
   the claims that reach unanimous support (304 → 79). By 0.85 only 14 real
   claims out of 452 are still in a 5/5 cluster; by 0.90 there are 4. A filter
   that keeps 0.9% of the claims is not a filter, it is a sampler.
2. **Purity improves slowly.** The supported share among the survivors rises
   21.7% → 30.4% → 42.9%, but that is bought entirely by shrinking the set.
3. **The contradiction rate does not fall.** 16.4% → 10.1% → 21.4% → 0.0%, with
   the last cell resting on four claims. Within noise it is flat. Claims all five
   samples agree on and Wikipedia denies are not artefacts of a loose similarity
   threshold — they are agreements, and no threshold can undo an agreement.
4. **The 0.60 default is not the confound.** It was chosen to maximise coverage
   at a defensible similarity level, and the strict thresholds confirm that
   tightening it trades coverage for nothing.

## Caveats

- The `contradicted` labels come from the same `relabel.py --max-chars 3000`
  run that the A4 audit flagged, so both sides of this comparison inherit that
  truncation. Package B (`llm_adjudication/part4_40_blind.jsonl`) is the
  experiment that isolates it: 40 claims, each under a 3,000-character and a
  full-text condition.
- The 0.85 and 0.90 cells are small (14 and 4 real claims); their rates carry
  wide uncertainty and should be read as "no better", not as "better".
- `cluster_id` is unique only within a prompt. The comparison block originally
  counted `cluster_id` file-wide, which merged clusters across prompts and
  reported 51/65/64/54 clusters with mean sizes 2.42/1.20/1.03/1.01. It now
  counts `(pid, cluster_id)`; the numbers above are from the fixed block.
