"""Evaluate cached conformal-factuality baselines."""

from __future__ import annotations

import hashlib
import math
import random
import shutil
import tempfile
from collections.abc import Sequence
from pathlib import Path

from confqa.common.io import load_config
from confqa.common.metrics import summarize_factuality
from confqa.common.paths import REPO_ROOT, RESULTS
from confqa.common.results import file_sha256, run_result

from .conformal import conformal_threshold, rank_score, retain_claims
from .data import FactResponse, load_factscore_responses, load_factscore_split

DEFAULT_CONFIG = REPO_ROOT / "configs" / "factuality.yaml"


def _resolve_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


def _path_label(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _ids_sha256(ids: Sequence[str]) -> str:
    payload = "\n".join(sorted(ids)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def select_calibration(
    responses: Sequence[FactResponse],
    fraction: float,
    *,
    seed: int,
) -> tuple[FactResponse, ...]:
    """Select a deterministic, nested calibration subset."""
    if not 0.0 < fraction <= 1.0:
        raise ValueError("calibration fraction must be in (0, 1]")
    ordered = sorted(responses, key=lambda response: response.pid)
    count = math.floor(len(ordered) * fraction + 0.5)
    count = max(1, min(count, len(ordered)))
    if count > len(ordered):
        raise ValueError("not enough calibration responses")

    rng = random.Random(seed)
    rng.shuffle(ordered)
    return tuple(sorted(ordered[:count], key=lambda response: response.pid))


def filtered_records(
    responses: Sequence[FactResponse],
    threshold: float,
) -> list[dict]:
    """Convert filtered responses into the shared metric record shape."""
    records = []
    for response in responses:
        retained_ids = {claim.cid for claim in retain_claims(response.claims, threshold)}
        records.append(
            {
                "pid": response.pid,
                "claims": [
                    {
                        "correct": claim.correct,
                        "retained": claim.cid in retained_ids,
                    }
                    for claim in response.claims
                ],
            }
        )
    return records


def _metric_values(records: Sequence[dict]) -> tuple[float, float, float, float]:
    summary = summarize_factuality(records)
    return (
        float(summary["all_correct_nonempty"]),
        float(summary["retention"]),
        float(summary["empty_rate"]),
        float(summary["all_correct_vacuous"]),
    )


def bootstrap_intervals(
    records: Sequence[dict],
    *,
    n_boot: int,
    level: float,
    seed: int,
) -> dict[str, tuple[float, float]]:
    """Bootstrap test responses jointly for all three headline metrics."""
    if not records:
        raise ValueError("records must not be empty")
    if n_boot <= 0:
        raise ValueError("n_boot must be positive")
    if not 0.0 < level < 1.0:
        raise ValueError("level must be in (0, 1)")

    rng = random.Random(seed)
    samples = []
    for _ in range(n_boot):
        sample = [records[rng.randrange(len(records))] for _ in records]
        samples.append(_metric_values(sample))

    lo_index = int((1.0 - level) / 2.0 * n_boot)
    hi_index = int((1.0 + level) / 2.0 * n_boot) - 1
    keys = ("all_correct_ci", "retention_ci", "empty_ci", "all_correct_vacuous_ci")
    return {
        key: (
            sorted(values[index] for values in samples)[lo_index],
            sorted(values[index] for values in samples)[hi_index],
        )
        for index, key in enumerate(keys)
    }


def evaluate_threshold(
    responses: Sequence[FactResponse],
    threshold: float,
    *,
    n_boot: int,
    level: float,
    seed: int,
) -> dict:
    """Calculate headline factuality metrics and bootstrap intervals."""
    records = filtered_records(responses, threshold)
    summary = summarize_factuality(records)
    intervals = bootstrap_intervals(
        records,
        n_boot=n_boot,
        level=level,
        seed=seed,
    )
    total_claims = sum(len(record["claims"]) for record in records)
    retained_claims = sum(claim["retained"] for record in records for claim in record["claims"])
    return {
        "n_responses": len(records),
        "n_claims": total_claims,
        "n_retained_claims": retained_claims,
        "all_correct_nonempty": summary["all_correct_nonempty"],
        "all_correct_nonempty_ci": list(intervals["all_correct_ci"]),
        "all_correct_vacuous": summary["all_correct_vacuous"],
        "all_correct_vacuous_ci": list(intervals["all_correct_vacuous_ci"]),
        "retention": summary["retention"],
        "retention_ci": list(intervals["retention_ci"]),
        "empty_rate": summary["empty_rate"],
        "empty_rate_ci": list(intervals["empty_ci"]),
    }


def _calculate_runs(
    config_path: str | Path,
    calibration_fractions: Sequence[float],
) -> list[dict]:
    """Calculate configured alpha runs for each calibration fraction."""
    path = _resolve_path(config_path)
    document = load_config(path)
    settings = document.get("factuality")
    if not isinstance(settings, dict):
        raise ValueError("config must contain a factuality object")
    fractions = [float(fraction) for fraction in calibration_fractions]
    if not fractions or len(fractions) != len(set(fractions)):
        raise ValueError("calibration fractions must be non-empty and unique")

    scored_path = _resolve_path(settings["scored_path"])
    split_path = _resolve_path(settings["split_path"])
    responses = load_factscore_responses(
        scored_path,
        score_field=settings.get("score_field", "frequency-score"),
    )
    splits = load_factscore_split(responses, split_path)
    if "calib_pool" not in splits or "test" not in splits:
        raise ValueError("split must contain calib_pool and test")

    test = splits["test"]
    test_ids = [response.pid for response in test]

    runs = []
    for fraction in fractions:
        calibration = select_calibration(
            splits["calib_pool"],
            fraction,
            seed=int(document["seed"]),
        )
        calibration_ids = [response.pid for response in calibration]
        calibration_ranks = [rank_score(response.claims) for response in calibration]
        for alpha in settings["alphas"]:
            alpha = float(alpha)
            threshold = conformal_threshold(calibration_ranks, alpha)
            metrics = evaluate_threshold(
                test,
                threshold,
                n_boot=int(settings["bootstrap_samples"]),
                level=float(settings["bootstrap_level"]),
                seed=int(document["seed"]),
            )
            runs.append(
                {
                    "alpha": alpha,
                    "calib_frac": fraction,
                    "payload": {
                        "threshold": threshold,
                        "confidence_method": settings["confidence_method"],
                        "required_correct_fraction": float(settings["required_correct_fraction"]),
                        "n_calibration": len(calibration),
                        "calibration_ids": calibration_ids,
                        "calibration_ids_sha256": _ids_sha256(calibration_ids),
                        "test_ids_sha256": _ids_sha256(test_ids),
                        "scored_file": _path_label(scored_path),
                        "scored_sha256": file_sha256(scored_path),
                        "split_file": _path_label(split_path),
                        "split_sha256": file_sha256(split_path),
                        "upstream_commit": settings["upstream_commit"],
                        **metrics,
                    },
                }
            )
    return runs


def calculate_baseline(config_path: str | Path = DEFAULT_CONFIG) -> list[dict]:
    """Calculate both configured alpha runs without writing result files."""
    path = _resolve_path(config_path)
    settings = load_config(path)["factuality"]
    return _calculate_runs(path, [float(settings["baseline_calib_frac"])])


def calculate_grid(config_path: str | Path = DEFAULT_CONFIG) -> list[dict]:
    """Calculate the alpha by calibration-size grid."""
    path = _resolve_path(config_path)
    settings = load_config(path)["factuality"]
    return _calculate_runs(path, settings["calib_fracs"])


def _run_and_persist(
    config_path: str | Path,
    runs: Sequence[dict],
    *,
    results_dir: str | Path | None,
) -> list[Path]:
    """Persist a batch of results generated against one repository snapshot."""
    path = _resolve_path(config_path)
    document = load_config(path)
    settings = document["factuality"]
    target_dir = Path(results_dir) if results_dir is not None else RESULTS
    staged_outputs = []

    # Generate all files outside the checkout so writing one result does not
    # make a later result's provenance dirty.
    with tempfile.TemporaryDirectory(prefix="confqa-fact-grid-") as staging:
        for run in runs:
            staged = run_result(
                pipeline="fact",
                alpha=run["alpha"],
                calib_frac=run["calib_frac"],
                payload=run["payload"],
                config=_path_label(path),
                model=settings["model"],
                seed=int(document["seed"]),
                results_dir=staging,
            )
            staged_outputs.append(staged)

        outputs = []
        for staged in staged_outputs:
            target = target_dir / staged.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(staged, target)
            outputs.append(target)
    return outputs


def run_baseline(
    config_path: str | Path = DEFAULT_CONFIG,
    *,
    results_dir: str | Path | None = None,
) -> list[Path]:
    """Calculate and persist both configured baseline results."""
    path = _resolve_path(config_path)
    return _run_and_persist(
        path,
        calculate_baseline(path),
        results_dir=results_dir,
    )


def run_grid(
    config_path: str | Path = DEFAULT_CONFIG,
    *,
    results_dir: str | Path | None = None,
) -> list[Path]:
    """Calculate and persist the complete comparison grid."""
    path = _resolve_path(config_path)
    return _run_and_persist(
        path,
        calculate_grid(path),
        results_dir=results_dir,
    )
