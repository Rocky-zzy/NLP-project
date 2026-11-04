import math

import pytest

from confqa.factuality.conformal import (
    ALL_CORRECT_SENTINEL,
    claim_score,
    conformal_threshold,
    rank_score,
    retain_claims,
)
from confqa.factuality.data import FactClaim


def _claim(cid: int, score: float, annotation: str) -> FactClaim:
    return FactClaim(
        cid=cid,
        text=f"claim {cid}",
        annotation=annotation,
        score=score,
        noise=0.0,
    )


def test_rank_score_stops_at_first_incorrect_claim():
    claims = [
        _claim(0, 5.0, "Y"),
        _claim(1, 4.0, "S"),
        _claim(2, 2.0, "N"),
        _claim(3, 1.0, "Y"),
    ]

    assert rank_score(claims) == 2.0


def test_rank_score_all_correct_uses_sentinel():
    claims = [_claim(0, 2.0, "Y"), _claim(1, 1.0, "S")]

    assert rank_score(claims) == ALL_CORRECT_SENTINEL


def test_rank_score_empty_response_uses_sentinel():
    assert rank_score([]) == ALL_CORRECT_SENTINEL


def test_conformal_threshold_uses_finite_sample_quantile():
    ranks = [-100000.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0]

    assert conformal_threshold(ranks, alpha=0.1) == 9.0
    assert conformal_threshold(ranks, alpha=0.2) == 8.0


def test_too_few_calibration_examples_fails():
    with pytest.raises(ValueError, match="need at least"):
        conformal_threshold([1.0] * 9, alpha=0.05)


def test_retain_claims_includes_threshold_and_preserves_order():
    claims = [_claim(0, 3.0, "N"), _claim(1, 2.0, "Y"), _claim(2, 1.0, "Y")]

    retained = retain_claims(claims, threshold=2.0)

    assert [claim.cid for claim in retained] == [0, 1]


def test_claim_score_includes_cached_noise():
    claim = FactClaim(cid=0, text="x", annotation="Y", score=2.0, noise=-0.1)

    assert math.isclose(claim_score(claim), 1.9)


def test_real_upstream_threshold_matches_cached_result():
    from confqa.factuality.data import DEFAULT_SCORED_PATH, load_factscore_responses

    expected_path = DEFAULT_SCORED_PATH.with_name("factscore_a=1_alpha=0.15_conf=frequency+gpt.txt")
    if not DEFAULT_SCORED_PATH.exists() or not expected_path.exists():
        pytest.skip("upstream FActScore cache is not available")

    responses = load_factscore_responses(score_field="frequency+gpt-score")
    ranks = [rank_score(response.claims) for response in responses]
    expected = float(expected_path.read_text(encoding="utf-8"))

    assert math.isclose(conformal_threshold(ranks, alpha=0.15), expected)
