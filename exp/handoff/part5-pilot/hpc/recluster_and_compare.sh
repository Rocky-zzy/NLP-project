#!/usr/bin/env bash
# Run on the HPC login node from the repository root.
# Produces the strict-clustering comparison (B2) and the inputs for Package B.
set -euo pipefail

ROOT="${PROJECT_ROOT:-/hpc2ssd/JH_DATA/spooler/aiaa4051_077/NLP-project}"
PY="${PROJECT_ROOT:-/hpc2ssd/JH_DATA/spooler/aiaa4051_077}/envs/confqa/bin/python"
OUT="${HOME}/part5-handoff"

cd "$ROOT"
mkdir -p "$OUT"

echo "== 1. original artifacts =="
ls -l cache/ext/clusters.jsonl cache/ext/labels_wiki.jsonl
cp cache/ext/clusters.jsonl cache/ext/labels_wiki.jsonl "$OUT/"

echo "== 2. strict clustering reruns (0.75 / 0.85 / 0.90) =="
for t in 0.75 0.85 0.90; do
  echo "-- threshold $t"
  PYTHONPATH=src "$PY" -m confqa.extension.cluster \
    --claims cache/h3/ext_claims.jsonl \
    --baseline cache/h3/ext_baseline_scores.jsonl \
    --encoder cross-encoder/stsb-roberta-large \
    --threshold "$t" \
    --out "cache/ext/clusters_t${t}.jsonl"
  cp "cache/ext/clusters_t${t}.jsonl" "$OUT/"
done

echo "== 3. comparison table =="
PYTHONPATH=src "$PY" - "$OUT" <<'PY'
import json, sys
from collections import Counter
from pathlib import Path

out = Path(sys.argv[1])
labels = {}
for line in (out / "labels_wiki.jsonl").read_text(encoding="utf-8").splitlines():
    if line.strip():
        r = json.loads(line); labels[(r["pid"], r["cid"])] = r["verdict"]

def load(path):
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]

print(f"{'threshold':>10} {'claims':>7} {'clusters':>9} {'mean size':>10} {'share sup=1.0':>14} {'contradicted@1.0':>18}")
for name in ["clusters.jsonl", "clusters_t0.75.jsonl", "clusters_t0.85.jsonl", "clusters_t0.90.jsonl"]:
    p = out / name
    if not p.exists():
        continue
    rows = load(p)
    sizes = Counter(r["cluster_id"] for r in rows)
    hi = [r for r in rows if r["support"] >= 0.999]
    contra = sum(1 for r in hi if labels.get((r["pid"], r["cid"])) == "contradicted")
    thr = "0.60" if name == "clusters.jsonl" else name.replace("clusters_t", "").replace(".jsonl", "")
    print(f"{thr:>10} {len(rows):7d} {len(sizes):9d} {sum(sizes.values())/max(1,len(sizes)):10.2f} "
          f"{len(hi)/max(1,len(rows)):14.3f} {contra}/{len(hi)} = {contra/max(1,len(hi)):.3f}")
PY

echo "== 4. files to transfer =="
ls -l "$OUT"
sha256sum "$OUT"/*.jsonl