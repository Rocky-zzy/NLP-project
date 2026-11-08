"""Calibrate and compare the two claim scorers on the Part 4 data.

Baseline  : frequency_score from the H3 judge (range -5..5)
Extension : support, the fraction of the five responses containing an
            equivalent claim (range 0..1)

Both use the same claims, the same labels and the same split-conformal
procedure, so the comparison is at an identical sampling budget.

    python -m confqa.extension.evaluate --clusters cache/ext/clusters.jsonl \
        --labels cache/ext/labels.jsonl --out-dir exp/results
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

from confqa.common.metrics import summarize_factuality
from confqa.common.results import run_result

METHODS = {
    "baseline": "baseline_frequency",
    "support": "support",
}


def _label_value(row: dict) -> bool | None:
    """Accept both the judge format (correct) and the wiki format (verdict)."""
    if "correct" in row:
        return bool(row["correct"])
    verdict = row.get("verdict")
    if verdict == "supported":
        return True
    if verdict == "not_claim":
        return None
    return False  # contradicted, absent, no_source


def load_rows(clusters: Path, labels: Path) -> dict[str, list[dict]]:
    label_map = {}
    for line in labels.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        value = _label_value(row)
        if value is not None:
            label_map[(row["pid"], int(row["cid"]))] = value

    by_pid: dict[str, list[dict]] = defaultdict(list)
    for line in clusters.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        key = (row["pid"], int(row["cid"]))
        if key not in label_map:
            continue  # not a factual claim, excluded from the metric
        row["correct"] = label_map[key]
        by_pid[row["pid"]].append(row)
    return by_pid


def rank_score(claims: list[dict], field: str) -> float:
    """Smallest threshold that lets an incorrect claim through (B's definition)."""
    if not claims:
        return -math.inf
    scores = sorted((float(c[field]) for c in claims), reverse=True)
    for threshold in scores:
        kept = [c for c in claims if float(c[field]) >= threshold]
        if not all(c["correct"] for c in kept):
            return threshold
    return -math.inf


def conformal_threshold(scores: list[float], alpha: float) -> float:
    n = len(scores)
    level = math.ceil((n + 1) * (1.0 - alpha)) / n
    if level > 1.0:
        raise ValueError(f"{n} calibration responses are too few for alpha={alpha}")
    return sorted(scores)[math.ceil(level * n) - 1]


def evaluate(
    rows: dict[str, list[dict]], split: dict, field: str, alpha: float
) -> tuple[dict, float]:
    test_ids = set(split["test"])
    calib_ids = set(split["dev"]) | set(split["calib_pool"])

    calib_scores = [rank_score(rows[pid], field) for pid in sorted(calib_ids) if pid in rows]
    threshold = conformal_threshold(calib_scores, alpha)

    records = []
    for pid in sorted(test_ids):
        if pid not in rows:
            continue
        records.append(
            {
                "claims": [
                    {"correct": c["correct"], "retained": float(c[field]) >= threshold}
                    for c in rows[pid]
                ]
            }
        )
    summary = summarize_factuality(records)
    summary["threshold"] = threshold
    summary["n_calibration"] = len(calib_scores)
    return summary, threshold


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clusters", default="cache/ext/clusters.jsonl")
    parser.add_argument("--labels", default="cache/ext/labels.jsonl")
    parser.add_argument("--split", default="data/splits/factscore.json")
    parser.add_argument("--out-dir", default="exp/results")
    parser.add_argument("--alphas", default="0.1,0.2")
    args = parser.parse_args(argv)

    rows = load_rows(Path(args.clusters), Path(args.labels))
    split = json.loads(Path(args.split).read_text(encoding="utf-8"))["splits"]
    alphas = [float(x) for x in args.alphas.split(",")]

    for method, field in METHODS.items():
        for alpha in alphas:
            summary, threshold = evaluate(rows, split, field, alpha)
            payload = {
                "method": method,
                "field": field,
                "threshold": threshold,
                "n_responses": summary["n"],
                "n_claims": sum(len(rows[pid]) for pid in split["test"] if pid in rows),
                "all_correct_vacuous": summary["all_correct_vacuous"],
                "all_correct_nonempty": summary["all_correct_nonempty"],
                "retention": summary["retention"],
                "empty_rate": summary["empty_rate"],
            }
            path = run_result(
                pipeline="ext",
                alpha=alpha,
                name=f"ext_{method}__a{alpha:g}.json",
                payload=payload,
                results_dir=args.out_dir,
            )
            print(
                f"{method:9s} a={alpha}: thr={threshold:7.3f} "
                f"vac={summary['all_correct_vacuous']:.3f} "
                f"nonempty={summary['all_correct_nonempty']:.3f} "
                f"ret={summary['retention']:.3f} empty={summary['empty_rate']:.3f} -> {path.name}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
