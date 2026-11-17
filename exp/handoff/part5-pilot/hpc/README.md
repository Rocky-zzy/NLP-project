# HPC steps (blocked locally)

The workstation cannot reach the cluster (one configured host times out, the
other rejects the key), so these steps must be run on the HPC. Nothing here
touches tracked files: new cluster files go to `cache/ext/` (git-ignored) and
copies to `~/part5-handoff/`.

## What is needed

1. `cache/ext/clusters.jsonl` and `cache/ext/labels_wiki.jsonl` — the original
   clustering and the grounded labels, for Package B.
2. Re-clustering at 0.75 / 0.85 / 0.90 — the B2 sensitivity analysis.
3. The printed comparison table, which can be pasted back even if no file is
   transferred.

## Run

```bash
cd /hpc2ssd/JH_DATA/spooler/aiaa4051_077/NLP-project
git fetch origin && git pull --ff-only
bash exp/handoff/part5-pilot/hpc/recluster_and_compare.sh
```

The script prints, per threshold: target claims, clusters, mean cluster size,
share of claims at support 1.0, and the contradiction rate among support-1.0
claims under the existing grounded labels.

## Notes

- Encoder is `cross-encoder/stsb-roberta-large`, the same checkpoint as the
  original run; the script records it on the command line.
- No new LLM calls are needed: re-clustering only changes the support score, and
  the grounded labels attach to target claims, not to clusters.
- Do not choose a threshold because it yields a nicer factuality number. The
  decision rule is fixed in the plan: 0.60 is the original, 0.85 and 0.90 are
  the strict conditions, 0.75 is a sensitivity point.