"""Build the Part 4 re-adjudication package (Package B).

Blocked until the cluster artifacts arrive:
  cache/ext/clusters.jsonl      target claims with support scores
  cache/ext/labels_wiki.jsonl   grounded verdicts (private, used only for selection)

Writes into llm_adjudication/: part4_40_blind.jsonl, part4_private_mapping.json.
Nothing about the labels goes into the evaluator-facing file.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent / "llm_adjudication"
CLUSTERS = ROOT / "cache/ext/clusters.jsonl"
LABELS = ROOT / "cache/ext/labels_wiki.jsonl"
NAMES = ROOT / "data/factscore_names.txt"
WIKI = ROOT / "data/wiki_cache"
SEED = 20261117
PREFIX_3K = 3000


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    missing = [str(p) for p in (CLUSTERS, LABELS) if not p.exists()]
    if missing:
        raise SystemExit(
            "blocked: missing " + ", ".join(missing) + "\n"
            "Run exp/handoff/part5-pilot/hpc/recluster_and_compare.sh on the cluster "
            "and copy the two files back into cache/ext/."
        )

    rows = read_jsonl(CLUSTERS)
    verdict = {(r["pid"], r["cid"]): r["verdict"] for r in read_jsonl(LABELS)}
    names = [n.strip() for n in NAMES.read_text(encoding="utf-8").splitlines() if n.strip()]

    def name_for(pid: str) -> str:
        return names[int(pid.split("-")[1])]

    def evidence_for(pid: str) -> tuple[str, str]:
        path = WIKI / (name_for(pid).replace(" ", "_") + ".json")
        if not path.exists():
            return "", ""
        blob = json.loads(path.read_text(encoding="utf-8"))
        return blob.get("title", ""), blob.get("extract", "")

    high = [r for r in rows if r["support"] >= 0.999 and verdict.get((r["pid"], r["cid"])) == "contradicted"]
    rest = [r for r in rows if r not in high]

    rng = random.Random(SEED)
    rng.shuffle(high)
    rng.shuffle(rest)
    chosen = high[:20] + rest[:20]
    if len(chosen) < 40:
        raise SystemExit(f"not enough claims: high={len(high)} rest={len(rest)}")

    records, private = [], []
    for r in chosen:
        title, extract = evidence_for(r["pid"])
        for condition, text in (("first_3000", extract[:PREFIX_3K]), ("full", extract)):
            records.append(
                {
                    "claim": r["text"],
                    "evidence_title": title,
                    "evidence_text": text,
                    "source_url": ("https://en.wikipedia.org/wiki/" + title.replace(" ", "_")) if title else None,
                    "retrieval_date": "2026-11-08",
                    "revision_id": None,
                    "temporal_context": (
                        "The claim comes from a Qwen2.5-14B-Instruct biography generated in 2026. "
                        "The evidence was retrieved from English Wikipedia on 2026-11-08."
                    ),
                }
            )
            private.append(
                {
                    "pid": r["pid"],
                    "cid": r["cid"],
                    "support": r["support"],
                    "grounded_verdict": verdict.get((r["pid"], r["cid"])),
                    "condition": condition,
                    "evidence_chars": len(text),
                }
            )

    order = list(range(len(records)))
    rng.shuffle(order)
    blind, mapping = [], {}
    for i, idx in enumerate(order):
        blind_id = f"X{i + 1:03d}"
        blind.append({"blind_id": blind_id, **records[idx]})
        mapping[blind_id] = private[idx]

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "part4_40_blind.jsonl").write_text(
        "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in blind), encoding="utf-8"
    )
    (OUT / "part4_private_mapping.json").write_text(
        json.dumps(mapping, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"wrote {len(blind)} blind records ({len(chosen)} claims x 2 conditions)")
    print("private mapping keeps pid/cid/support/verdict/condition — never hand it to a model")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
