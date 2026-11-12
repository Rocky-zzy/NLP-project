"""Run the ConU calibration-size grid from the verified A3 and A4 artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from time import perf_counter

import numpy as np

from confqa.common import metrics, plots, results

A3 = Path("cache/a3_500_m20")
A4 = Path("cache/a4_filter_audit/summary.json")
CONFIG = Path("configs/conu_a5.json")


def load_inputs(root, config):
    sources = {}

    def read(path):
        body = (root / path).read_bytes()
        sources[path.as_posix()] = hashlib.sha256(body).hexdigest()
        return body

    plan = json.loads(read(A3 / "plan.json"))
    split = json.loads(read(A3 / "split.json"))
    manifest = json.loads(read(A3 / "conformal/manifest.json"))
    question_path = A3 / "conformal/questions.jsonl"
    records = [json.loads(line) for line in read(question_path).split(b"\n") if line]
    a4 = json.loads(read(A4))
    if (
        sources[question_path.as_posix()] != manifest["outputs"]["questions.jsonl"]
        or split != plan["split"]
        or any(
            sources[(A3 / name).as_posix()] != a4["a3_input_sha256"][name]
            for name in ("plan.json", "split.json", "conformal/manifest.json")
        )
        or config["correctness_threshold"] != a4["correctness_threshold"]
        or config["seed"] != split["selection_seed"]
        or split["selection_uses_model_outcomes"]
        or config["drop_unanswerable"]
        or config["model"].casefold() != plan["model"].casefold()
    ):
        raise ValueError("A3/A4 provenance does not match the A5 config or saved data.")

    by_id = {row["qid"]: row for row in records}
    cal_ids, test_ids = split["calibration_ids"], split["test_ids"]
    if (
        len(records) != 500
        or len(by_id) != 500
        or len(cal_ids) != 250
        or len(test_ids) != 250
        or set(cal_ids + test_ids) != set(by_id)
    ):
        raise ValueError("Expected 500 distinct questions with a frozen 250/250 partition.")
    calibration = [by_id[qid] for qid in cal_ids]
    test = [by_id[qid] for qid in test_ids]
    if (
        any(row["role"] != "calibration" for row in calibration)
        or any(row["role"] != "test" for row in test)
        or any(len(row["samples"]) != 20 for row in records)
    ):
        raise ValueError("Unexpected A3 roles or candidate counts.")
    return calibration, test, a4, sources


def calibrate(calibration, alpha):
    """Use the pinned ConU quantile on every calibration question."""
    n = len(calibration)
    level = math.ceil((n + 1) * (1 - alpha)) / n
    scores = [row["reference_nonconformity"] for row in calibration]
    return float(np.quantile(scores, level, method="higher")), level


def summarize(test, threshold, bootstrap):
    flags, sizes = [], []
    for row in test:
        indices = [i for i, score in enumerate(row["sample_nonconformity"]) if score <= threshold]
        flags.append(any(row["acceptable_samples"][i] for i in indices))
        sizes.append(len(indices))
    return {
        "n_test": len(test),
        "covered_count": sum(flags),
        "coverage": metrics.coverage(flags),
        "avg_set_size": metrics.avg_set_size(sizes),
        "coverage_ci": metrics.bootstrap_ci(flags, **bootstrap),
        "avg_set_size_ci": metrics.bootstrap_ci(sizes, **bootstrap),
    }


def run_grid(input_root, output_dir):
    config = json.loads(CONFIG.read_bytes())
    calibration, test, a4, sources = load_inputs(input_root, config)
    eligible_test = [row for row in test if row["has_acceptable_sample"]]
    a4_reference = {row["alpha"]: row for row in a4["results"] if row["no_filter"]}
    n_total = len(calibration) + len(test)
    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.iterdir()):
        raise ValueError("Use an empty result directory for a new A5 run.")
    if results.git_commit() == "unknown" or results.git_dirty():
        raise ValueError("Run A5 from a clean Git checkout to record reportable provenance.")

    records = []
    for n_cal in config["calibration_sizes"]:
        subset = calibration[:n_cal]
        for alpha in config["alphas"]:
            started = perf_counter()
            threshold, level = calibrate(subset, alpha)
            point = summarize(test, threshold, config["bootstrap"])
            if n_cal == len(calibration):
                reference = a4_reference[alpha]
                if (threshold, level, point["covered_count"], point["avg_set_size"]) != (
                    reference["q_hat"],
                    reference["q_level"],
                    reference["covered_count"],
                    reference["average_set_size_slots"],
                ):
                    raise ValueError("Full-pool A5 results differ from the A4 unfiltered run.")

            payload = {
                **point,
                "dataset": config["dataset"],
                "threshold": threshold,
                "quantile_level": level,
                "n_total": n_total,
                "n_used": n_cal + len(test),
                "n_unused_calibration": len(calibration) - n_cal,
                "n_dropped_unanswerable": 0,
                "n_unanswerable_total": a4["counts"]["excluded"],
                "n_unanswerable_test": len(test) - len(eligible_test),
                "n_unanswerable_in_selected_calibration": sum(
                    not row["has_acceptable_sample"] for row in subset
                ),
                "n_calibration_pool": len(calibration),
                "n_calibration_used": n_cal,
                "calib_ratio_of_total": n_cal / n_total,
                "calibration_selection": config["calibration_selection"],
                "calibration_ids_used": [row["qid"] for row in subset],
                "split_file": (A3 / "split.json").as_posix(),
                "coverage_scope": "all_fixed_test_unfiltered_calibration",
                "eligible_test": summarize(eligible_test, threshold, config["bootstrap"]),
                "set_size_unit": "response slots including duplicate text",
                "correctness_threshold": config["correctness_threshold"],
                "bootstrap": {
                    **config["bootstrap"],
                    "unit": "test question",
                    "method": "percentile bootstrap with fixed calibration",
                },
                "input_sha256": sources,
                "runtime": {"python": sys.version.split()[0], "numpy": np.__version__},
            }
            path = results.run_result(
                pipeline="conu",
                alpha=alpha,
                calib_frac=n_cal / len(calibration),
                config=CONFIG,
                model=config["model"],
                seed=config["seed"],
                payload=payload,
                results_dir=output_dir,
                elapsed_s=round(perf_counter() - started, 3),
            )
            records.append(json.loads(path.read_bytes()))
            print(
                f"{path.name}: {point['covered_count']}/{point['n_test']}, "
                f"mean size {point['avg_set_size']:.3f}, q={threshold:.6g}",
                flush=True,
            )
    return records


def plot_grid(records, output):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter

    alphas = sorted({record["alpha"] for record in records})
    fig, axes = plt.subplots(1, len(alphas), figsize=(9.4, 4.7), sharex=True, sharey=True)
    for ax, alpha in zip(axes, alphas, strict=True):
        color = plots.ALPHA_COLORS[alpha]
        groups = defaultdict(list)
        for record in records:
            if record["alpha"] == alpha:
                point = (
                    record["avg_set_size"],
                    record["coverage"],
                    tuple(record["avg_set_size_ci"]),
                    tuple(record["coverage_ci"]),
                )
                groups[point].append(record["n_calibration_used"])
        for (x, y, (xl, xh), (yl, yh)), counts in groups.items():
            ax.errorbar(
                x,
                y,
                xerr=[[x - xl], [xh - x]],
                yerr=[[y - yl], [yh - y]],
                color=color,
                fmt="o",
                markersize=7,
                capsize=5,
                linewidth=1.5,
                zorder=3,
            )
            label = ", ".join(str(n) for n in sorted(counts))
            ax.annotate(
                f"{label} calibration questions",
                (x, yh),
                xytext=(0, 9),
                textcoords="offset points",
                ha="center",
                fontsize=9,
            )
        ax.axhline(1 - alpha, color=color, linestyle="--", linewidth=1, alpha=0.7)
        ax.set_title(f"{1 - alpha:.0%} target coverage", loc="left", fontweight="bold")
        ax.grid(True, color="#e6e9ed", linewidth=0.7)
        ax.spines[["top", "right"]].set_visible(False)
        ax.yaxis.set_major_formatter(PercentFormatter(1, decimals=0))
    low = min(row["avg_set_size_ci"][0] for row in records)
    high = max(row["avg_set_size_ci"][1] for row in records)
    axes[0].set(xlim=(max(0, low - 0.45), min(20.1, high + 0.45)), ylim=(0.78, 1.01))
    axes[0].set_ylabel("Coverage on the fixed test set")
    fig.supxlabel("Mean answer-set size (response slots)", y=0.12)
    fig.suptitle("ConU coverage vs. answer-set size", x=0.10, ha="left", fontweight="bold")
    fig.text(
        0.10,
        0.88,
        "TriviaQA, 250 held-out questions. Error bars show 95% bootstrap intervals.",
        fontsize=9,
        color="#475569",
    )
    fig.text(
        0.10,
        0.04,
        "Dashed lines mark target coverage. Coincident settings share one marker.",
        fontsize=9,
        color="#475569",
    )
    fig.subplots_adjust(left=0.10, right=0.97, bottom=0.22, top=0.77, wspace=0.14)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=200, facecolor="white")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--figure", type=Path, required=True)
    args = parser.parse_args()
    records = run_grid(args.input_root, args.output_dir)
    plot_grid(records, args.figure)


if __name__ == "__main__":
    main()
