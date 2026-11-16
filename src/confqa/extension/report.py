"""Build the Part 4 extension comparison figure from result JSON files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from confqa.common.paths import FIGURES, RESULTS

LABEL_SETS = ("weak", "grounded")
METHODS = ("baseline", "support")
CHECKED_ALPHAS = (0.1, 0.2)
ALPHA = 0.1
COMPARED_FIELDS = (
    "n_responses",
    "n_claims",
    "threshold",
    "all_correct_vacuous",
    "all_correct_nonempty",
    "retention",
    "empty_rate",
)
CATEGORIES = ("non_empty_correct", "empty", "non_empty_error")
CATEGORY_LABELS = {
    "non_empty_correct": "Non-empty, all claims correct",
    "empty": "Empty response",
    "non_empty_error": "Non-empty, contains an error",
}
CATEGORY_COLORS = {
    "non_empty_correct": "#2F6DAE",
    "empty": "#B8BEC7",
    "non_empty_error": "#D17B28",
}


def _read_cell(directory: Path, label_set: str, method: str, alpha: float) -> dict:
    path = directory / label_set / f"ext_{method}__a{alpha:g}.json"
    if not path.exists():
        raise FileNotFoundError(f"missing extension result: {path}")
    record = json.loads(path.read_text(encoding="utf-8"))
    if record.get("pipeline") != "ext":
        raise ValueError(f"{path.name} is not an extension result")
    if record.get("reportable") is not True:
        raise ValueError(f"{path.name} is not reportable")
    if record.get("method") != method:
        raise ValueError(f"{path.name} reports method {record.get('method')!r}")
    return record


def _count(value: float, n: int, field: str, path: Path) -> int:
    count = value * n
    if abs(count - round(count)) > 1e-6:
        raise ValueError(f"{path.name}: {field} is not a whole number of responses")
    return int(round(count))


def load_extension_results(results_dir: str | Path | None = None) -> list[dict]:
    """Load one reportable record per setting, after checking both targets agree."""
    directory = Path(results_dir) if results_dir is not None else Path(RESULTS) / "extension"
    records = []
    for label_set in LABEL_SETS:
        for method in METHODS:
            cells = [_read_cell(directory, label_set, method, alpha) for alpha in CHECKED_ALPHAS]
            fingerprint = [{field: cell[field] for field in COMPARED_FIELDS} for cell in cells]
            if fingerprint[0] != fingerprint[1]:
                raise ValueError(f"{label_set}/{method}: the two targets disagree")
            record = cells[0]
            source = Path(directory / label_set / f"ext_{method}__a{ALPHA:g}.json")
            n = int(record["n_responses"])
            vacuous = _count(record["all_correct_vacuous"], n, "all_correct_vacuous", source)
            empty = _count(record["empty_rate"], n, "empty_rate", source)
            records.append(
                {
                    "label_set": label_set,
                    "method": method,
                    "n_responses": n,
                    "n_claims": int(record["n_claims"]),
                    "retention": float(record["retention"]),
                    "threshold": float(record["threshold"]),
                    "counts": {
                        "non_empty_correct": vacuous - empty,
                        "empty": empty,
                        "non_empty_error": n - vacuous,
                    },
                }
            )
    return records


def plot_extension_comparison(records: list[dict], output: Path) -> Path:
    """Stacked outcome composition plus retention, one row per setting."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    labels = [f"{r['label_set']}\n{r['method']}" for r in records]
    y = list(range(len(records)))[::-1]

    fig, (left, right) = plt.subplots(
        1, 2, figsize=(10.2, 4.4), gridspec_kw={"width_ratios": [1.55, 1.0]}
    )

    running = [0] * len(records)
    for category in CATEGORIES:
        widths = [r["counts"][category] for r in records]
        left.barh(
            y,
            widths,
            left=running,
            height=0.62,
            color=CATEGORY_COLORS[category],
            label=CATEGORY_LABELS[category],
            edgecolor="white",
            linewidth=0.8,
        )
        running = [a + b for a, b in zip(running, widths, strict=True)]
    left.set_yticks(y, labels)
    left.set_xlabel("Test responses")
    left.set_title("Outcome composition", loc="left", fontweight="bold")
    left.legend(
        loc="lower center", bbox_to_anchor=(0.5, -0.42), ncol=3, frameon=False, fontsize=8.5
    )
    left.grid(True, axis="x", color="#E6E9ED", linewidth=0.7)
    left.set_axisbelow(True)
    left.spines[["top", "right"]].set_visible(False)
    for yi, row in zip(y, records, strict=True):
        left.text(
            row["n_responses"] + 0.4, yi, f"n={row['n_responses']}", va="center", fontsize=8.5
        )
    left.set_xlim(0, max(r["n_responses"] for r in records) + 4)

    retention = [100 * r["retention"] for r in records]
    colors = ["#2F6DAE" if r["method"] == "support" else "#7A8797" for r in records]
    right.barh(y, retention, height=0.62, color=colors, edgecolor="white", linewidth=0.8)
    for yi, r in zip(y, records, strict=True):
        kept = round(r["retention"] * r["n_claims"])
        right.text(
            100 * r["retention"] + 1.2,
            yi,
            f"{100 * r['retention']:.1f}%  ({kept}/{r['n_claims']})",
            va="center",
            fontsize=8.5,
        )
    right.set_yticks(y, [""] * len(records))
    right.set_xlabel("Claims retained (%)")
    right.set_title("Retention", loc="left", fontweight="bold")
    right.set_xlim(0, 100)
    right.grid(True, axis="x", color="#E6E9ED", linewidth=0.7)
    right.set_axisbelow(True)
    right.spines[["top", "right"]].set_visible(False)

    fig.suptitle(
        "Part 4: cross-response support versus the judge-frequency baseline",
        x=0.02,
        ha="left",
        fontweight="bold",
        fontsize=12.5,
    )
    fig.text(
        0.02,
        0.915,
        "FActScore test split, alpha = 0.1 (the 0.2 cells are identical: both thresholds sit on the same atom).",
        fontsize=8.5,
        color="#475569",
    )
    fig.subplots_adjust(left=0.14, right=0.97, bottom=0.3, top=0.82, wspace=0.12)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=200, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", default=None)
    parser.add_argument("--out", default=str(Path(FIGURES) / "extension_comparison.png"))
    args = parser.parse_args(argv)
    records = load_extension_results(args.results_dir)
    path = plot_extension_comparison(records, Path(args.out))
    for record in records:
        counts = record["counts"]
        print(
            f"{record['label_set']:8s} {record['method']:8s} n={record['n_responses']} "
            f"correct={counts['non_empty_correct']} empty={counts['empty']} "
            f"error={counts['non_empty_error']} retention={record['retention']:.3f}"
        )
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
