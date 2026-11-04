import json

import pytest

from confqa.factuality.cases import (
    analyze_primary_cases,
    audit_cached_exclusions,
    build_case_views,
    load_survey_outputs,
    summarize_case_views,
    summarize_claim_outcomes,
    summarize_correct_claim_features,
    summarize_score_bands,
)
from confqa.factuality.data import DEFAULT_SCORED_PATH, FactClaim, FactResponse


def _response(pid: str, scores: tuple[float, ...], labels: tuple[str, ...]) -> FactResponse:
    claims = tuple(
        FactClaim(
            cid=index,
            text=f"claim {index}",
            annotation=label,
            score=score,
            noise=0.0,
        )
        for index, (score, label) in enumerate(zip(scores, labels, strict=True))
    )
    return FactResponse(pid=pid, prompt="prompt", claims=claims)


def test_survey_reconstruction_uses_c_factual_option(tmp_path):
    path = tmp_path / "survey.json"
    path.write_text(
        json.dumps(
            {
                "data": [
                    {"Answer 1": "filtered", "Answer 2": "original", "C-factal option": "1"},
                    {"Answer 1": "original", "Answer 2": "filtered", "C-factal option": "2"},
                ]
            }
        ),
        encoding="utf-8",
    )

    outputs = load_survey_outputs(path, response_count=5)

    assert outputs == {
        "factscore-0003": ("original", "filtered"),
        "factscore-0004": ("original", "filtered"),
    }


def test_case_summary_has_mutually_exclusive_counts():
    responses = [
        _response("factscore-0000", (5.0, 1.0), ("Y", "N")),
        _response("factscore-0001", (1.0, 1.0), ("Y", "N")),
        _response("factscore-0002", (5.0, 4.0), ("N", "Y")),
    ]

    cases = build_case_views(
        responses,
        threshold=4.5,
        survey_outputs={"factscore-0000": ("original", "filtered")},
    )

    assert summarize_case_views(cases) == {
        "n_test": 3,
        "n_empty": 1,
        "n_all_correct_nonempty": 1,
        "n_retained_unaccepted": 1,
        "n_retained_false": 1,
        "n_retained_unverifiable": 0,
        "n_original_available": 1,
    }
    assert summarize_claim_outcomes(cases)["Y"] == {
        "total": 3,
        "retained": 1,
        "dropped": 2,
        "retention": 1 / 3,
    }
    assert summarize_score_bands(cases)["5"]["correct"] == {
        "total": 1,
        "retained": 1,
        "dropped": 0,
    }
    features = summarize_correct_claim_features(cases)
    assert features["correct_retained"]["total"] == 1
    assert features["correct_dropped"]["total"] == 2


def test_real_case_counts_and_cache_audit():
    if not DEFAULT_SCORED_PATH.exists():
        pytest.skip("upstream FActScore cache is not available")

    analysis = analyze_primary_cases()

    assert analysis["summary"] == {
        "n_test": 25,
        "n_empty": 7,
        "n_all_correct_nonempty": 17,
        "n_retained_unaccepted": 1,
        "n_retained_false": 1,
        "n_retained_unverifiable": 0,
        "n_original_available": 14,
    }
    assert analysis["cache_audit"]["n_empty_claim_sets"] == 0
    assert analysis["cache_audit"]["n_missing_merged_responses"] == 0
    assert analysis["cache_audit"]["n_missing_accepted_claims"] == 0
    assert analysis["cache_audit"]["n_empty_accepted_claims"] == 4
    assert analysis["cache_audit"]["n_abstain_outputs"] == 4
    assert analysis["cache_audit"]["n_parse_failures"] is None
    assert analysis["claim_outcomes"]["Y"]["retained"] == 40
    assert analysis["claim_outcomes"]["S"]["retained"] == 4
    assert analysis["claim_outcomes"]["N"]["retained"] == 1
    assert analysis["claim_outcomes"]["U"]["retained"] == 0
    assert analysis["score_bands"]["5"]["correct"] == {
        "total": 66,
        "retained": 44,
        "dropped": 22,
    }
    assert analysis["score_bands"]["4"]["correct"] == {
        "total": 12,
        "retained": 0,
        "dropped": 12,
    }
    assert analysis["score_bands"]["1_to_3"]["correct"] == {
        "total": 45,
        "retained": 0,
        "dropped": 45,
    }
    features = analysis["claim_features"]
    assert features["correct_retained"]["total"] == 44
    assert features["correct_dropped"]["total"] == 91
    assert features["correct_retained"]["work_event_or_award"]["count"] == 7
    assert features["correct_dropped"]["work_event_or_award"]["count"] == 21
    assert features["correct_retained"]["compound_statement"]["count"] == 5
    assert features["correct_dropped"]["compound_statement"]["count"] == 16
    assert features["correct_retained"]["reference_dependent"]["count"] == 3
    assert features["correct_dropped"]["reference_dependent"]["count"] == 17
    assert features["correct_retained"]["subjective_annotation"]["count"] == 4
    assert features["correct_dropped"]["subjective_annotation"]["count"] == 20


def test_cache_audit_rejects_malformed_merged_file(tmp_path):
    path = tmp_path / "merged.jsonl"
    path.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="data array"):
        audit_cached_exclusions([], path)
