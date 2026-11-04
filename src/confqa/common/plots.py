"""Trade-off plots built from exp/results/*.json.

Matplotlib is imported lazily so that the core package (and the unit tests)
stay usable on a cluster login node without a plotting stack.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from .paths import REPO_ROOT

ALPHA_COLORS = {0.1: "#3B6EA5", 0.2: "#D9822B", 0.3: "#3F8F5A", 0.4: "#8E6C8A"}


def _pyplot():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def load_results(pattern: str | Path = "exp/results/*.json") -> list[dict]:
    """Load every result json matching a glob (relative to the repo root)."""
    path = Path(pattern)
    if not path.is_absolute():
        path = REPO_ROOT / path
    records = []
    for item in sorted(path.parent.glob(path.name)):
        records.append(json.loads(item.read_text(encoding="utf-8")))
    return records


def _color(alpha: float) -> str:
    return ALPHA_COLORS.get(round(alpha, 2), "#555555")


def _finish(ax, xlabel: str, ylabel: str, title: str, out_path: Path) -> Path:
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(True, color="#E8E8E8", linewidth=0.6)
    handles, labels = ax.get_legend_handles_labels()
    if handles:
        ax.legend(frameon=False)
    fig = ax.figure
    fig.tight_layout()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    fig.clf()
    return out_path


def plot_coverage_vs_size(
    records: Iterable[dict],
    out_path: str | Path = "figures/coverage_vs_size.png",
    title: str = "Short-form: coverage vs. answer-set size",
) -> Path:
    """One line per alpha; error bars are the bootstrap CI recorded in the result."""
    plt = _pyplot()
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    rows = [r for r in records if "coverage" in r and "avg_set_size" in r]

    for alpha in sorted({r["alpha"] for r in rows if r.get("alpha") is not None}):
        group = sorted(
            (r for r in rows if r.get("alpha") == alpha),
            key=lambda r: r["avg_set_size"],
        )
        xs = [r["avg_set_size"] for r in group]
        ys = [r["coverage"] for r in group]
        low = [r["coverage"] - r["coverage_ci"][0] if r.get("coverage_ci") else 0.0 for r in group]
        high = [r["coverage_ci"][1] - r["coverage"] if r.get("coverage_ci") else 0.0 for r in group]
        color = _color(alpha)
        ax.errorbar(
            xs,
            ys,
            yerr=[low, high],
            marker="o",
            capsize=3,
            color=color,
            label=f"1-alpha = {1 - alpha:.2f}",
        )
        ax.axhline(1 - alpha, linestyle=":", linewidth=1, color=color, alpha=0.7)

    _finish(ax, "average set size", "coverage", title, Path(out_path))
    return Path(out_path)


def plot_retention_vs_factuality(
    records: Iterable[dict],
    out_path: str | Path = "figures/retention_vs_factuality.png",
    title: str = "Long-form: factuality vs. retained information",
) -> Path:
    """x = retained fraction of claims, y = responses whose retained claims are all correct."""
    plt = _pyplot()
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    rows = [r for r in records if "retention" in r and "all_correct_nonempty" in r]

    for alpha in sorted({r["alpha"] for r in rows if r.get("alpha") is not None}):
        group = sorted(
            (r for r in rows if r.get("alpha") == alpha),
            key=lambda r: r["retention"],
        )
        color = _color(alpha)
        ax.plot(
            [r["retention"] for r in group],
            [r["all_correct_nonempty"] for r in group],
            marker="o",
            color=color,
            label=f"1-alpha = {1 - alpha:.2f}",
        )
        ax.axhline(1 - alpha, linestyle=":", linewidth=1, color=color, alpha=0.7)

    _finish(ax, "retained fraction of claims", "all retained claims correct", title, Path(out_path))
    return Path(out_path)
