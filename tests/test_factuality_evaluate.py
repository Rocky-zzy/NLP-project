import json

import pytest

from confqa.factuality.data import FactClaim, FactResponse
from confqa.factuality.evaluate import (
    calculate_baseline,
    evaluate_threshold,
    filtered_records,
    select_calibration,
)


def _response(pid: str, *, correct_first: bool = True) -> FactResponse:
    if correct_first:
        annotations = ("Y", "N")
        scores = (5.0, 1.0)
    else:
        annotations = ("N", "Y")
        scores = (5.0, 4.0)
    claims = tuple(
        FactClaim(
            cid=index,
            text=f"claim {index}",
            annotation=annotation,
            score=score,
            noise=0.0,
        )
        for index, (annotation, score) in enumerate(zip(annotations, scores, strict=True))
    )
    return FactResponse(pid=pid, prompt="prompt", claims=claims)


def test_calibration_selection_is_deterministic_and_nested():
    responses = [_response(f"factscore-{index:04d}") for index in range(20)]

    half = select_calibration(responses, 0.5, seed=0)
    three_quarters = select_calibration(responses, 0.75, seed=0)

    assert [response.pid for response in half] == [
        response.pid for response in select_calibration(responses, 0.5, seed=0)
    ]
    assert {response.pid for response in half} < {response.pid for response in three_quarters}


def test_threshold_filtering_and_metrics():
    responses = [_response("factscore-0000"), _response("factscore-0001", correct_first=False)]

    records = filtered_records(responses, threshold=4.5)
    metrics = evaluate_threshold(
        responses,
        threshold=4.5,
        n_boot=200,
        level=0.95,
        seed=0,
    )

    assert [claim["retained"] for claim in records[0]["claims"]] == [True, False]
    assert metrics["n_responses"] == 2
    assert metrics["n_claims"] == 4
    assert metrics["n_retained_claims"] == 2
    assert metrics["all_correct_nonempty"] == 0.5
    assert metrics["retention"] == 0.5
    assert metrics["empty_rate"] == 0.0


def test_synthetic_baseline_writes_two_results(tmp_path):
    records = []
    for index in range(30):
        records.append(
            {
                "prompt": f"prompt {index}",
                "claims": [
                    {
                        "subclaim": "correct",
                        "annotation": "Y",
                        "frequency-score": 5.0,
                        "noise": 0.0,
                    },
                    {
                        "subclaim": "incorrect",
                        "annotation": "N",
                        "frequency-score": float(index % 5),
                        "noise": 0.0,
                    },
                ],
            }
        )
    scored_path = tmp_path / "scores.jsonl"
    scored_path.write_text(json.dumps({"data": records}), encoding="utf-8")
    split_path = tmp_path / "split.json"
    split_path.write_text(
        json.dumps(
            {
                "splits": {
                    "test": [f"factscore-{index:04d}" for index in range(10)],
                    "dev": [],
                    "calib_pool": [f"factscore-{index:04d}" for index in range(10, 30)],
                }
            }
        ),
        encoding="utf-8",
    )
    config_path = tmp_path / "factuality.yaml"
    config_path.write_text(
        "\n".join(
            [
                "seed: 0",
                "factuality:",
                f"  scored_path: {scored_path}",
                f"  split_path: {split_path}",
                "  score_field: frequency-score",
                "  confidence_method: frequency",
                "  required_correct_fraction: 1.0",
                "  alphas: [0.1, 0.2]",
                "  baseline_calib_frac: 0.5",
                "  bootstrap_samples: 100",
                "  bootstrap_level: 0.95",
                "  model: upstream-cached:gpt-4",
                "  upstream_commit: test-commit",
            ]
        ),
        encoding="utf-8",
    )

    runs = calculate_baseline(config_path)

    assert [run["alpha"] for run in runs] == [0.1, 0.2]
    assert all(run["payload"]["n_calibration"] == 10 for run in runs)
    assert all(run["payload"]["n_responses"] == 10 for run in runs)
    assert all(len(run["payload"]["all_correct_nonempty_ci"]) == 2 for run in runs)


def test_real_baseline_computes():
    from confqa.factuality.data import DEFAULT_SCORED_PATH
    from confqa.factuality.evaluate import DEFAULT_CONFIG

    if not DEFAULT_SCORED_PATH.exists():
        pytest.skip("upstream FActScore cache is not available")

    runs = calculate_baseline(DEFAULT_CONFIG)

    assert [run["alpha"] for run in runs] == [0.1, 0.2]
    assert all(run["payload"]["n_calibration"] == 10 for run in runs)
    assert all(run["payload"]["n_responses"] == 25 for run in runs)
