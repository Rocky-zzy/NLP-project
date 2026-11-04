"""Minimal split-conformal filtering for cached claim scores."""

from __future__ import annotations

import math
from collections.abc import Sequence

from .data import CORRECT_ANNOTATIONS, FactClaim

ALL_CORRECT_SENTINEL = -100_000.0


def claim_score(claim: FactClaim) -> float:
    """Reproduce the upstream score-plus-tie-break comparison."""
    return claim.score + claim.noise


def rank_score(
    claims: Sequence[FactClaim],
    *,
    required_correct_fraction: float = 1.0,
) -> float:
    """Return the first threshold that admits too many incorrect claims.

    Thresholds are the observed score-plus-noise values in descending order.
    An empty or entirely correct response never crosses the error boundary and
    receives the upstream sentinel.
    """
    if not 0.0 < required_correct_fraction <= 1.0:
        raise ValueError("required_correct_fraction must be in (0, 1]")
    if not claims:
        return ALL_CORRECT_SENTINEL

    thresholds = sorted((claim_score(claim) for claim in claims), reverse=True)
    for threshold in thresholds:
        retained = [claim for claim in claims if claim_score(claim) >= threshold]
        correct_fraction = sum(claim.annotation in CORRECT_ANNOTATIONS for claim in retained)
        correct_fraction /= len(retained)
        if correct_fraction < required_correct_fraction:
            return threshold
    return ALL_CORRECT_SENTINEL


def conformal_threshold(
    rank_scores: Sequence[float],
    alpha: float,
) -> float:
    """Compute the finite-sample split-conformal upper quantile."""
    n = len(rank_scores)
    if n == 0:
        raise ValueError("rank_scores must not be empty")
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be in (0, 1)")

    target_index = math.ceil((n + 1) * (1.0 - alpha))
    if target_index > n:
        minimum = math.ceil(1.0 / alpha - 1.0)
        raise ValueError(
            f"{n} calibration responses are insufficient for alpha={alpha}; need at least {minimum}"
        )
    return sorted(float(score) for score in rank_scores)[target_index - 1]


def retain_claims(claims: Sequence[FactClaim], threshold: float) -> tuple[FactClaim, ...]:
    """Keep claims at or above the calibrated threshold in source order."""
    return tuple(claim for claim in claims if claim_score(claim) >= threshold)
