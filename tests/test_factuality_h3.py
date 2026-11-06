import json

import pytest

from confqa.common.io import read_jsonl
from confqa.factuality.h3 import (
    BREAKDOWN_PROMPT,
    H3ParseError,
    build_fact_responses,
    load_ext_responses,
    parse_claim_output,
    parse_judgment_output,
    run_h3,
)


class FakeClient:
    def __init__(
        self,
        *,
        bad_split_response: str | None = None,
        bad_judge_response: str | None = None,
    ):
        self.bad_split_response = bad_split_response
        self.bad_judge_response = bad_judge_response
        self.calls = 0

    def complete(self, messages, *, model, temperature=0.0, max_tokens=1000):
        self.calls += 1
        user = messages[-1]["content"]
        if user.startswith(BREAKDOWN_PROMPT):
            response = user.removeprefix(BREAKDOWN_PROMPT)
            if response == self.bad_split_response:
                return "not json"
            return (
                "```jsonl\n"
                '{"subclaim":"The sky is blue.","gpt-score":1}\n'
                '{"subclaim":"Grass is green.","gpt-score":0.8}\n'
                "```"
            )

        comparison = user.split("\n\nThe text is:\n", 1)[1].lower()
        if comparison == self.bad_judge_response:
            return "not json"
        sky_score = 1 if "sky is blue" in comparison else 0
        if "grass is green" in comparison:
            grass_score = 1
        elif "grass is red" in comparison:
            grass_score = -1
        else:
            grass_score = 0
        return "\n".join(
            [
                json.dumps({"id": 0, "score": sky_score}),
                json.dumps({"id": 1, "score": grass_score}),
            ]
        )


def test_parse_claim_output_accepts_code_fence():
    claims = parse_claim_output('```jsonl\n{"subclaim":"one","gpt-score":0.9}\n{"text":"two"}\n```')

    assert [(claim.cid, claim.text) for claim in claims] == [
        (0, "one"),
        (1, "two"),
    ]
    assert claims[0].gpt_score == 0.9


def test_parse_claim_output_rejects_partial_bad_line():
    with pytest.raises(H3ParseError, match="line 2"):
        parse_claim_output('{"subclaim":"one"}\n{"gpt-score":0.5}')


def test_parse_judgment_output_requires_every_claim_once():
    with pytest.raises(H3ParseError, match="missing claim ids"):
        parse_judgment_output('{"id":0,"score":1}', expected_claim_ids=[0, 1])

    with pytest.raises(H3ParseError, match="invalid score"):
        parse_judgment_output('{"id":0,"score":2}', expected_claim_ids=[0])

    with pytest.raises(H3ParseError, match="integer id and score"):
        parse_judgment_output('{"id":0,"score":1.5}', expected_claim_ids=[0])

    with pytest.raises(H3ParseError, match="unknown claim id"):
        parse_judgment_output('{"id":1,"score":1}', expected_claim_ids=[0])

    with pytest.raises(H3ParseError, match="repeats claim id"):
        parse_judgment_output(
            '{"id":0,"score":1}\n{"id":0,"score":0}',
            expected_claim_ids=[0],
        )


def test_fake_client_runs_h3_end_to_end(tmp_path):
    records = load_ext_responses("examples/h3/ext_responses.jsonl")
    summary = run_h3(
        records,
        FakeClient(),
        output_dir=tmp_path,
        model="fake-model",
        target_response_ids=(0,),
    )

    assert summary.prompts == 1
    assert summary.split_responses == 5
    assert summary.target_rows == 1
    assert summary.failure_rows == 0
    assert len(list(read_jsonl(tmp_path / "ext_claims.jsonl"))) == 5
    judgments = list(read_jsonl(tmp_path / "ext_judgments.jsonl"))
    assert len(judgments[0]["claims"][0]["judgments"]) == 5
    scores = list(read_jsonl(tmp_path / "ext_baseline_scores.jsonl"))
    assert scores[0]["claims"][0]["frequency_score"] == 5
    assert scores[0]["claims"][0]["support_rate"] == 1.0
    assert scores[0]["claims"][1]["frequency_score"] == 2
    assert scores[0]["claims"][1]["support_rate"] == 0.6


def test_split_failure_is_recorded_and_target_is_skipped(tmp_path):
    records = load_ext_responses("examples/h3/ext_responses.jsonl")

    summary = run_h3(
        records,
        FakeClient(bad_split_response=records[0].responses[4]),
        output_dir=tmp_path,
        model="fake-model",
        target_response_ids=(4,),
    )

    assert summary.split_responses == 4
    assert summary.target_rows == 0
    assert summary.failure_rows == 1
    failures = list(read_jsonl(tmp_path / "ext_h3_failures.jsonl"))
    assert failures[0]["stage"] == "claim_split"


def test_scores_join_labels_for_shared_conformal_pipeline(tmp_path):
    records = load_ext_responses("examples/h3/ext_responses.jsonl")
    run_h3(
        records,
        FakeClient(),
        output_dir=tmp_path,
        model="fake-model",
        target_response_ids=(0,),
    )
    score_rows = list(read_jsonl(tmp_path / "ext_baseline_scores.jsonl"))
    labels = {
        ("h3-demo-0001", 0, 0): "Y",
        ("h3-demo-0001", 0, 1): "N",
    }

    responses = build_fact_responses(score_rows, labels)

    assert len(responses) == 1
    assert [claim.correct for claim in responses[0].claims] == [True, False]
    assert [claim.score for claim in responses[0].claims] == [5.0, 2.0]

    with pytest.raises(ValueError, match="missing labels"):
        build_fact_responses(score_rows, {("h3-demo-0001", 0, 0): "Y"})


def test_judge_failure_is_recorded_and_partial_target_is_skipped(tmp_path):
    records = load_ext_responses("examples/h3/ext_responses.jsonl")

    summary = run_h3(
        records,
        FakeClient(bad_judge_response=records[0].responses[0].lower()),
        output_dir=tmp_path,
        model="fake-model",
        target_response_ids=(0,),
    )

    assert summary.split_responses == 5
    assert summary.target_rows == 0
    assert summary.failure_rows == 1
    failures = list(read_jsonl(tmp_path / "ext_h3_failures.jsonl"))
    assert failures[0]["stage"] == "judge"
