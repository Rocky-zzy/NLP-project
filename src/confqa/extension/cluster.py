"""Score target claims by cross-response support (Part 4, step 2-3).

Claims of the five responses are compared pairwise with the same cross-encoder
the short-form line uses, equivalent claims are merged, and each target claim
gets support = (number of distinct responses in its cluster) / 5.

    python -m confqa.extension.cluster \
        --claims cache/h3/ext_claims.jsonl \
        --baseline cache/h3/ext_baseline_scores.jsonl \
        --out cache/ext/clusters.jsonl --threshold 0.6
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def load_claims(path: Path) -> dict[str, dict[int, list[dict]]]:
    by_prompt: dict[str, dict[int, list[dict]]] = defaultdict(dict)
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        by_prompt[row["pid"]][int(row["response_id"])] = row["claims"]
    return by_prompt


def load_baseline(path: Path) -> dict[str, dict[int, dict]]:
    out: dict[str, dict[int, dict]] = defaultdict(dict)
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        for claim in row["claims"]:
            out[row["pid"]][int(claim["cid"])] = claim
    return out


def score_pairs(encoder, texts_a: list[str], texts_b: list[str], batch: int) -> list[float]:
    if not texts_a:
        return []
    scores = encoder.predict(list(zip(texts_a, texts_b, strict=True)), batch_size=batch)
    return [float(s) for s in scores]


def clusters_for_prompt(
    claims_by_response: dict[int, list[dict]],
    encoder,
    threshold: float,
    batch: int,
) -> tuple[list[tuple[int, int]], list[float]]:
    """Return flat claim list and union-find edges above the threshold."""
    flat: list[tuple[int, int, str]] = []
    for rid in sorted(claims_by_response):
        for claim in claims_by_response[rid]:
            flat.append((rid, int(claim["cid"]), str(claim["text"])))

    pairs_a, pairs_b, edges = [], [], []
    for i in range(len(flat)):
        for j in range(i + 1, len(flat)):
            if flat[i][0] == flat[j][0]:
                continue
            pairs_a.append(flat[i][2])
            pairs_b.append(flat[j][2])
            edges.append((i, j))

    scores = score_pairs(encoder, pairs_a, pairs_b, batch)
    kept = [(edges[k], scores[k]) for k in range(len(edges)) if scores[k] >= threshold]
    return flat, kept


def build_components(count: int, edges: list[tuple[int, int]]) -> dict[int, list[int]]:
    """Union-find over claim indices; returns root -> member indices."""
    parent = list(range(count))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in edges:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    members: dict[int, list[int]] = defaultdict(list)
    for index in range(count):
        members[find(index)].append(index)
    return members


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claims", default="cache/h3/ext_claims.jsonl")
    parser.add_argument("--baseline", default="cache/h3/ext_baseline_scores.jsonl")
    parser.add_argument("--out", default="cache/ext/clusters.jsonl")
    parser.add_argument("--threshold", type=float, default=0.6)
    parser.add_argument("--encoder", default="cross-encoder/stsb-roberta-large")
    parser.add_argument("--batch", type=int, default=64)
    parser.add_argument("--target", type=int, default=0)
    args = parser.parse_args(argv)

    from sentence_transformers import CrossEncoder

    encoder = CrossEncoder(args.encoder, num_labels=1, device="cuda:0")
    by_prompt = load_claims(Path(args.claims))
    baseline = load_baseline(Path(args.baseline))

    out_rows = []
    for pid in sorted(by_prompt):
        flat, kept = clusters_for_prompt(by_prompt[pid], encoder, args.threshold, args.batch)
        members = build_components(len(flat), [edge for edge, _score in kept])
        root_of = {index: root for root, indexes in members.items() for index in indexes}

        for index, (rid, cid, text) in enumerate(flat):
            if rid != args.target:
                continue
            root = root_of[index]
            response_ids = {flat[m][0] for m in members[root]}
            base = baseline.get(pid, {}).get(cid, {})
            out_rows.append(
                {
                    "pid": pid,
                    "cid": cid,
                    "text": text,
                    "cluster_id": root,
                    "cluster_size": len(members[root]),
                    "support": len(response_ids) / max(1, len(by_prompt[pid])),
                    "member_response_ids": sorted(response_ids),
                    "baseline_frequency": base.get("frequency_score"),
                    "baseline_support_rate": base.get("support_rate"),
                }
            )
        print(
            f"{pid}: {len([1 for f in flat if f[0] == args.target])} target claims, {len(kept)} edges"
        )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in out_rows),
        encoding="utf-8",
        newline="\n",
    )
    print(f"wrote {out} ({len(out_rows)} target claims)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
