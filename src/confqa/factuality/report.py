"""Build report-ready factuality figures from result JSON files."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from confqa.common.paths import FIGURES, RESULTS

GRID_ALPHAS = (0.1, 0.2)
GRID_CALIB_FRACS = (0.5, 0.75, 1.0)
ALPHA_COLORS = {0.1: "#2F6DAE", 0.2: "#D17B28"}


def load_grid_results(results_dir: str | Path = RESULTS) -> list[dict]:
    """Load exactly one reportable result for each grid cell."""
    directory = Path(results_dir)
    records = {}
    for path in sorted(directory.glob("fact__a*__calib*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        key = (round(float(record["alpha"]), 2), round(float(record["calib_frac"]), 2))
        if key not in {(alpha, fraction) for alpha in GRID_ALPHAS for fraction in GRID_CALIB_FRACS}:
            continue
        if key in records:
            raise ValueError(f"duplicate grid result for alpha={key[0]}, calib={key[1]}")
        if record.get("pipeline") != "fact":
            raise ValueError(f"{path.name} is not a factuality result")
        if record.get("reportable") is not True:
            raise ValueError(f"{path.name} is not reportable")
        for field in (
            "retention",
            "retention_ci",
            "all_correct_nonempty",
            "all_correct_nonempty_ci",
            "empty_rate",
            "empty_rate_ci",
        ):
            if field not in record:
                raise ValueError(f"{path.name} is missing {field}")
        record["_source_file"] = path.name
        records[key] = record

    expected = {(alpha, fraction) for alpha in GRID_ALPHAS for fraction in GRID_CALIB_FRACS}
    missing = sorted(expected - set(records))
    extra = sorted(set(records) - expected)
    if missing or extra:
        raise ValueError(f"incomplete grid: missing={missing}, extra={extra}")
    return [records[key] for key in sorted(records)]


def _errors(record: dict, key: str, ci_key: str) -> tuple[list[float], list[float]]:
    value = float(record[key])
    low, high = (float(bound) for bound in record[ci_key])
    return [value - low, high - value], [low, high]


def plot_retention_vs_factuality(
    records: Sequence[dict],
    *,
    png_path: str | Path = FIGURES / "retention_vs_factuality.png",
    pdf_path: str | Path | None = FIGURES / "retention_vs_factuality.pdf",
) -> tuple[Path, Path | None]:
    """Plot retention against all-correct with 95% confidence intervals."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7.2, 4.8))
    for alpha in sorted({float(record["alpha"]) for record in records}):
        group = sorted(
            (record for record in records if float(record["alpha"]) == alpha),
            key=lambda record: (float(record["calib_frac"]), record["_source_file"]),
        )
        unique = {}
        for record in group:
            key = (
                round(float(record["retention"]), 6),
                round(float(record["all_correct_nonempty"]), 6),
            )
            unique.setdefault(key, []).append(record)

        color = ALPHA_COLORS.get(round(alpha, 2), "#555555")
        xs = []
        ys = []
        for (x, y), duplicates in unique.items():
            record = duplicates[0]
            xerr, _ = _errors(record, "retention", "retention_ci")
            yerr, _ = _errors(record, "all_correct_nonempty", "all_correct_nonempty_ci")
            ax.errorbar(
                x,
                y,
                xerr=[[xerr[0]], [xerr[1]]],
                yerr=[[yerr[0]], [yerr[1]]],
                fmt="o",
                color=color,
                ecolor=color,
                elinewidth=1.2,
                capsize=3,
                markersize=7,
                zorder=3,
            )
            sizes = "/".join(f"{record['n_calibration']:g}" for record in duplicates)
            ax.annotate(
                f"n={sizes}",
                (x, y),
                xytext=(7, 7),
                textcoords="offset points",
                color=color,
                fontsize=9,
                fontweight="bold",
            )
            xs.append(x)
            ys.append(y)

        ax.plot(xs, ys, color=color, linewidth=1.5, label=f"1-alpha = {1 - alpha:.1f}")
        ax.axhline(
            1 - alpha,
            color=color,
            linestyle=":",
            linewidth=1.0,
            alpha=0.75,
        )

    ax.set_xlabel("Retained fraction of claims")
    ax.set_ylabel("All retained claims correct")
    ax.set_title("Long-form factuality vs. retained information")
    ax.grid(True, color="#E7E7E7", linewidth=0.7)
    ax.legend(frameon=False, title="Target and method")
    fig.tight_layout()

    png_path = Path(png_path)
    png_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(png_path, dpi=220, bbox_inches="tight")
    saved_pdf = None
    if pdf_path is not None:
        saved_pdf = Path(pdf_path)
        saved_pdf.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(saved_pdf, bbox_inches="tight")
    plt.close(fig)
    return png_path, saved_pdf


def run_report(results_dir: str | Path = RESULTS) -> tuple[Path, Path | None]:
    """Load the grid and write the report figure."""
    records = load_grid_results(results_dir)
    return plot_retention_vs_factuality(records)
