"""Shared metrics for Project 1.

Every number that appears in the report should be produced here from
exp/results/*.json, never copied by hand. Stdlib only, so it also runs on a
cluster login node without the GPU environment.
"""

from __future__ import annotations

import random
from collections.abc import Sequence


def _mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else float("nan")


def coverage(flags: Sequence[bool]) -> float:
    """Fraction of examples whose prediction set contains >= 1 correct answer."""
    return _mean([1.0 if f else 0.0 for f in flags])


def avg_set_size(sizes: Sequence[int]) -> float:
    return _mean([float(s) for s in sizes])


def response_all_correct(retained: Sequence[dict]) -> bool:
    """True iff every retained claim is correct.

    An empty retained set is vacuously True, so callers must report empty
    responses separately; summarize_factuality does that.
    """
    return all(bool(c.get("correct")) for c in retained)


def summarize_factuality(records) -> dict:
    """Aggregate claim-level results into the three reported numbers.

    records: iterable of {"claims": [{"correct": bool, "retained": bool}, ...]}

    Returns:
        n: number of responses
        all_correct_nonempty: fraction of responses retaining >= 1 claim with
            all retained claims correct (the "factuality" headline number)
        retention: retained claims / total claims
        empty_rate: fraction of responses with no retained claim
    """
    n = good = empty = kept = total = 0
    for r in records:
        claims = r.get("claims") or []
        retained = [c for c in claims if c.get("retained")]
        n += 1
        total += len(claims)
        kept += len(retained)
        if not retained:
            empty += 1
        elif response_all_correct(retained):
            good += 1
    if n == 0:
        nan = float("nan")
        return {"n": 0, "all_correct_nonempty": nan, "retention": nan, "empty_rate": nan}
    return {
        "n": n,
        "all_correct_nonempty": good / n,
        "retention": kept / total if total else float("nan"),
        "empty_rate": empty / n,
    }


def bootstrap_ci(
    values: Sequence[float],
    n_boot: int = 10000,
    level: float = 0.95,
    seed: int = 0,
) -> tuple[float, float]:
    """Percentile bootstrap CI for the mean. Use it for small-n subsets."""
    vals = [float(v) for v in values]
    if not vals:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    n = len(vals)
    means = []
    for _ in range(n_boot):
        s = 0.0
        for _ in range(n):
            s += vals[rng.randrange(n)]
        means.append(s / n)
    means.sort()
    lo = means[int((1.0 - level) / 2.0 * n_boot)]
    hi = means[int((1.0 + level) / 2.0 * n_boot) - 1]
    return (lo, hi)


def summarize_coverage(flags: Sequence[bool], sizes: Sequence[int]) -> dict:
    """Bundle the two short-form numbers plus a CI for coverage."""
    return {
        "n": len(flags),
        "coverage": coverage(flags),
        "avg_set_size": avg_set_size(sizes),
        "coverage_ci": bootstrap_ci([1.0 if f else 0.0 for f in flags]),
    }
