# HPC steps

These were written while the workstation could not reach the cluster. The
inputs have since been recovered through the HPC file browser, so everything
here runs on any host that has `cache/`, and a GPU is not required: pass
`--device cpu` to `confqa.extension.cluster`. Results are in
[B2-thresholds.md](B2-thresholds.md). Nothing here touches tracked files: new
cluster files go to `cache/ext/` (git-ignored) and copies to
`~/part5-handoff/`.

## What is needed

1. `cache/ext/clusters.jsonl` and `cache/ext/labels_wiki.jsonl` — the original
   clustering and the grounded labels, for Package B.
2. Re-clustering at 0.75 / 0.85 / 0.90 — the B2 sensitivity analysis.
3. The printed comparison table, which can be pasted back even if no file is
   transferred.

## Run

```bash
cd <repository root>
git fetch origin && git pull --ff-only
bash exp/handoff/part5-pilot/hpc/recluster_and_compare.sh
```

The defaults assume the original layout (`/hpc2ssd/JH_DATA/spooler/aiaa4051_077`).
On a different machine, point it at the new paths:

```bash
PROJECT_ROOT=/path/to/NLP-project \
CONFQA_PY=/path/to/conda/env/bin/python \
bash exp/handoff/part5-pilot/hpc/recluster_and_compare.sh
```

The script stops immediately and lists any of the four cache files that are
missing. They are git-ignored, so a fresh clone has none of them; the rebuild
order is `generate` → `run_h3` → `cluster --threshold 0.6` → `relabel`, and the
last two need the vLLM endpoint.

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