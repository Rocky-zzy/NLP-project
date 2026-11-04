import json
from pathlib import Path

import pytest

from confqa.factuality.data import (
    DEFAULT_SCORED_PATH,
    DEFAULT_SPLIT_PATH,
    annotation_counts,
    load_factscore_responses,
    load_factscore_split,
)


def _write_wrapped(path: Path, records: list[dict]) -> Path:
    path.write_text(json.dumps({"data": records}), encoding="utf-8")
    return path


def _record(prompt: str = "Tell me a bio", annotation: str = "Y") -> dict:
    return {
        "prompt": prompt,
        "claims": [
            {
                "subclaim": "A claim.",
                "annotation": annotation,
                "frequency-score": 2.0,
                "noise": 0.1,
            }
        ],
    }


def test_loads_wrapped_json_with_positional_ids(tmp_path):
    path = _write_wrapped(tmp_path / "scores.jsonl", [_record(), _record("Second")])

    responses = load_factscore_responses(path)

    assert [response.pid for response in responses] == [
        "factscore-0000",
        "factscore-0001",
    ]
    assert responses[0].claims[0].score == 2.0
    assert responses[0].claims[0].noise == 0.1
    assert responses[0].claims[0].correct is True


def test_join_split_rejects_overlap(tmp_path):
    path = _write_wrapped(tmp_path / "scores.jsonl", [_record(), _record("Second")])
    responses = load_factscore_responses(path)
    split_path = tmp_path / "split.json"
    split_path.write_text(
        json.dumps(
            {
                "splits": {
                    "test": ["factscore-0000"],
                    "calib_pool": ["factscore-0000", "factscore-0001"],
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="overlap"):
        load_factscore_split(responses, split_path)


def test_missing_score_fails_fast(tmp_path):
    record = _record()
    del record["claims"][0]["noise"]
    path = _write_wrapped(tmp_path / "scores.jsonl", [record])

    with pytest.raises(ValueError, match="missing noise"):
        load_factscore_responses(path)


def test_real_input_matches_expected_shape():
    if not DEFAULT_SCORED_PATH.exists() or not DEFAULT_SPLIT_PATH.exists():
        pytest.skip("upstream FActScore cache is not available")

    responses = load_factscore_responses()
    splits = load_factscore_split(responses)

    assert len(responses) == 50
    assert sum(len(response.claims) for response in responses) == 408
    assert annotation_counts(responses) == {"N": 75, "S": 52, "U": 46, "Y": 235}
    assert {name: len(items) for name, items in splits.items()} == {
        "test": 25,
        "dev": 5,
        "calib_pool": 20,
    }
