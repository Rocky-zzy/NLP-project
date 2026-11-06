"""New-response claim splitting and frequency judging for the H3 handoff."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from confqa.common.io import read_jsonl, write_jsonl

from .data import VALID_ANNOTATIONS, FactClaim, FactResponse

BREAKDOWN_SYSTEM_PROMPT = (
    "You are a helpful assistant whose job is to break down your inputs into a "
    "set of small claims so that a human can easily check each one. Make sure "
    "that each claim is small and non-overlapping."
)
BREAKDOWN_PROMPT = (
    "Please breakdown the following input into a set of small, independent "
    "claims, and return the output as a jsonl, where each line is "
    "{subclaim:[CLAIM], gpt-score:[CONF]}.\n The confidence score [CONF] should "
    "represent your confidence in the claim, where a 1 is obvious facts and "
    "results like 'The earth is round' and '1+1=2'. A 0 is for claims that are "
    "very obscure or difficult for anyone to know, like the birthdays of "
    "non-notable people. The input is: "
)
JUDGMENT_PROMPT_PREFIX = (
    "You will get a list of claims and piece of text. For each claim, score "
    "whether the text supports, contradicts, or is unrelated to the claim. "
    "Directly return a jsonl, where each line is "
    '{"id":[CLAIM_ID], "score":[SCORE]}. Directly return the jsonl with no '
    "explanation or other formatting. For the [SCORE], return 1 for supports, "
    "-1 for contradicts, and 0 for unrelated. The claims are:\n"
)

JUDGMENT_LABELS = {-1: "contradict", 0: "unrelated", 1: "support"}


class ChatClient(Protocol):
    """Minimal interface implemented by a local or OpenAI-compatible client."""

    def complete(
        self,
        messages: Sequence[dict[str, str]],
        *,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 1000,
    ) -> str:
        """Return one assistant message."""


class H3ParseError(ValueError):
    """A model response that cannot be safely converted into H3 records."""

    def __init__(self, message: str, raw_output: str):
        super().__init__(message)
        self.raw_output = raw_output


@dataclass(frozen=True)
class ExtPrompt:
    pid: str
    prompt: str
    responses: tuple[str, ...]


@dataclass(frozen=True)
class ParsedClaim:
    cid: int
    text: str
    gpt_score: float | None = None


@dataclass(frozen=True)
class Judgment:
    cid: int
    response_id: int
    score: int

    @property
    def label(self) -> str:
        return JUDGMENT_LABELS[self.score]


@dataclass(frozen=True)
class H3Summary:
    prompts: int
    split_responses: int
    target_rows: int
    failure_rows: int


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _strict_integer(value: object) -> int:
    if isinstance(value, bool):
        raise ValueError("boolean is not an integer label")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError as exc:
            raise ValueError("string is not an integer") from exc
    raise ValueError("value is not an integer")


def _data_lines(raw_output: str) -> list[str]:
    stripped = raw_output.strip()
    if stripped.startswith("["):
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise H3ParseError(f"invalid JSON array: {exc.msg}", raw_output) from exc
        if not isinstance(parsed, list):
            raise H3ParseError("top-level JSON must be an array", raw_output)
        return [json.dumps(item, ensure_ascii=False) for item in parsed]

    lines = []
    for line in raw_output.splitlines():
        line = line.strip()
        if not line or line.startswith("```"):
            continue
        lines.append(line)
    if not lines:
        raise H3ParseError("model returned no JSONL data", raw_output)
    return lines


def parse_claim_output(raw_output: str) -> tuple[ParsedClaim, ...]:
    """Parse the breakdown model's JSONL and validate every line."""
    claims = []
    for line_number, line in enumerate(_data_lines(raw_output), start=1):
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise H3ParseError(
                f"invalid claim JSON on line {line_number}: {exc.msg}",
                raw_output,
            ) from exc
        if not isinstance(item, dict):
            raise H3ParseError(f"claim line {line_number} is not an object", raw_output)
        text = item.get("subclaim", item.get("text"))
        if not isinstance(text, str) or not text.strip():
            raise H3ParseError(
                f"claim line {line_number} has no non-empty subclaim",
                raw_output,
            )
        gpt_score = item.get("gpt-score")
        if gpt_score is not None:
            try:
                gpt_score = float(gpt_score)
            except (TypeError, ValueError) as exc:
                raise H3ParseError(
                    f"claim line {line_number} has a non-numeric gpt-score",
                    raw_output,
                ) from exc
            if not math.isfinite(gpt_score):
                raise H3ParseError(
                    f"claim line {line_number} has a non-finite gpt-score",
                    raw_output,
                )
        claims.append(
            ParsedClaim(
                cid=len(claims),
                text=text.strip(),
                gpt_score=gpt_score,
            )
        )
    if not claims:
        raise H3ParseError("claim output was empty", raw_output)
    return tuple(claims)


def parse_judgment_output(
    raw_output: str,
    *,
    expected_claim_ids: Sequence[int],
) -> dict[int, int]:
    """Parse and validate one support/contradict/unrelated response."""
    expected = set(expected_claim_ids)
    if not expected:
        raise ValueError("expected_claim_ids must not be empty")

    judgments = {}
    for line_number, line in enumerate(_data_lines(raw_output), start=1):
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise H3ParseError(
                f"invalid judgment JSON on line {line_number}: {exc.msg}",
                raw_output,
            ) from exc
        if not isinstance(item, dict):
            raise H3ParseError(
                f"judgment line {line_number} is not an object",
                raw_output,
            )
        try:
            cid = _strict_integer(item["id"])
            score = _strict_integer(item["score"])
        except (KeyError, TypeError, ValueError) as exc:
            raise H3ParseError(
                f"judgment line {line_number} must contain integer id and score",
                raw_output,
            ) from exc
        if score not in JUDGMENT_LABELS:
            raise H3ParseError(
                f"judgment line {line_number} has invalid score {score}",
                raw_output,
            )
        if cid not in expected:
            raise H3ParseError(
                f"judgment line {line_number} has unknown claim id {cid}",
                raw_output,
            )
        if cid in judgments:
            raise H3ParseError(
                f"judgment line {line_number} repeats claim id {cid}",
                raw_output,
            )
        judgments[cid] = score

    missing = sorted(expected - set(judgments))
    if missing:
        raise H3ParseError(f"judgments missing claim ids {missing}", raw_output)
    return judgments


def split_claims(
    client: ChatClient,
    *,
    response: str,
    model: str,
) -> tuple[ParsedClaim, ...]:
    """Ask the configured LLM client to decompose one response."""
    raw_output = client.complete(
        [
            {"role": "system", "content": BREAKDOWN_SYSTEM_PROMPT},
            {"role": "user", "content": BREAKDOWN_PROMPT + response},
        ],
        model=model,
        temperature=0.0,
        max_tokens=1000,
    )
    return parse_claim_output(raw_output)


def judge_claims(
    client: ChatClient,
    *,
    claims: Sequence[ParsedClaim],
    comparison_response: str,
    comparison_response_id: int,
    model: str,
) -> tuple[Judgment, ...]:
    """Judge all target claims against one comparison response."""
    claim_text = "\n".join(f"{claim.cid}: {claim.text}" for claim in claims)
    raw_output = client.complete(
        [
            {
                "role": "user",
                "content": (
                    JUDGMENT_PROMPT_PREFIX + claim_text + "\n\nThe text is:\n" + comparison_response
                ),
            }
        ],
        model=model,
        temperature=0.0,
        max_tokens=1000,
    )
    scores = parse_judgment_output(
        raw_output,
        expected_claim_ids=[claim.cid for claim in claims],
    )
    return tuple(
        Judgment(cid=cid, response_id=comparison_response_id, score=score)
        for cid, score in sorted(scores.items())
    )


def load_ext_responses(
    path: str | Path,
    *,
    expected_responses: int = 5,
) -> list[ExtPrompt]:
    """Load C's `ext_responses.jsonl` and enforce the sampling contract."""
    records = []
    seen_ids = set()
    for row in read_jsonl(path):
        pid = row.get("pid")
        prompt = row.get("prompt")
        responses = row.get("responses")
        if not isinstance(pid, str) or not pid:
            raise ValueError("ext response row has no pid")
        if pid in seen_ids:
            raise ValueError(f"duplicate ext response pid: {pid}")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError(f"{pid} has no prompt")
        if not isinstance(responses, list) or len(responses) != expected_responses:
            raise ValueError(f"{pid} must contain exactly {expected_responses} responses")
        if any(not isinstance(response, str) or not response.strip() for response in responses):
            raise ValueError(f"{pid} contains an empty response")
        seen_ids.add(pid)
        records.append(ExtPrompt(pid=pid, prompt=prompt, responses=tuple(responses)))
    if not records:
        raise ValueError("ext response file is empty")
    return records


def run_h3(
    records: Sequence[ExtPrompt],
    client: ChatClient,
    *,
    output_dir: str | Path,
    model: str,
    judge_model: str | None = None,
    target_response_ids: Sequence[int] | None = None,
    comparison_response_ids: Sequence[int] | None = None,
) -> H3Summary:
    """Run claim splitting, judging, and frequency aggregation."""
    if not records:
        raise ValueError("records must not be empty")
    response_count = len(records[0].responses)
    if any(len(record.responses) != response_count for record in records):
        raise ValueError("all prompts must use the same number of responses")

    targets = tuple(
        range(response_count)
        if target_response_ids is None
        else (int(response_id) for response_id in target_response_ids)
    )
    comparisons = tuple(
        range(response_count)
        if comparison_response_ids is None
        else (int(response_id) for response_id in comparison_response_ids)
    )
    valid_ids = set(range(response_count))
    if not targets or not comparisons:
        raise ValueError("target and comparison response ids must not be empty")
    if len(targets) != len(set(targets)) or len(comparisons) != len(set(comparisons)):
        raise ValueError("target and comparison response ids must be unique")
    if not set(targets) <= valid_ids or not set(comparisons) <= valid_ids:
        raise ValueError("target or comparison response id is out of range")

    judge_model = judge_model or model
    claim_rows = []
    judgment_rows = []
    score_rows = []
    failures = []
    split_results = {}

    for record in records:
        successful_splits = {}
        for response_id, response in enumerate(record.responses):
            try:
                claims = split_claims(client, response=response, model=model)
            except H3ParseError as exc:
                failures.append(
                    {
                        "schema_version": 1,
                        "stage": "claim_split",
                        "pid": record.pid,
                        "response_id": response_id,
                        "error_type": type(exc).__name__,
                        "message": str(exc),
                        "raw_output": exc.raw_output,
                    }
                )
                continue
            successful_splits[response_id] = claims
            claim_rows.append(
                {
                    "schema_version": 1,
                    "pid": record.pid,
                    "response_id": response_id,
                    "model": model,
                    "response_sha256": _sha256(response),
                    "breakdown_prompt_sha256": _sha256(BREAKDOWN_SYSTEM_PROMPT + BREAKDOWN_PROMPT),
                    "claims": [
                        {
                            "cid": claim.cid,
                            "text": claim.text,
                            **(
                                {"gpt_score": claim.gpt_score}
                                if claim.gpt_score is not None
                                else {}
                            ),
                        }
                        for claim in claims
                    ],
                }
            )
        split_results[record.pid] = successful_splits

    for record in records:
        for target_response_id in targets:
            claims = split_results[record.pid].get(target_response_id)
            if claims is None:
                continue
            judgments_by_cid = {claim.cid: [] for claim in claims}
            judge_failed = False
            try:
                for comparison_id in comparisons:
                    judgments = judge_claims(
                        client,
                        claims=claims,
                        comparison_response=record.responses[comparison_id],
                        comparison_response_id=comparison_id,
                        model=judge_model,
                    )
                    for judgment in judgments:
                        judgments_by_cid[judgment.cid].append(judgment)
            except H3ParseError as exc:
                failures.append(
                    {
                        "schema_version": 1,
                        "stage": "judge",
                        "pid": record.pid,
                        "target_response_id": target_response_id,
                        "comparison_response_id": comparison_id,
                        "error_type": type(exc).__name__,
                        "message": str(exc),
                        "raw_output": exc.raw_output,
                    }
                )
                judge_failed = True
            if judge_failed:
                continue

            judgment_rows.append(
                {
                    "schema_version": 1,
                    "pid": record.pid,
                    "target_response_id": target_response_id,
                    "comparison_response_ids": list(comparisons),
                    "model": model,
                    "judged_by": judge_model,
                    "judge_prompt_sha256": _sha256(JUDGMENT_PROMPT_PREFIX),
                    "claims": [
                        {
                            "cid": claim.cid,
                            "text": claim.text,
                            "judgments": [
                                {
                                    "response_id": judgment.response_id,
                                    "label": judgment.label,
                                    "score": judgment.score,
                                }
                                for judgment in judgments_by_cid[claim.cid]
                            ],
                        }
                        for claim in claims
                    ],
                }
            )
            score_rows.append(
                {
                    "schema_version": 1,
                    "pid": record.pid,
                    "target_response_id": target_response_id,
                    "prompt": record.prompt,
                    "claims": [
                        {
                            "cid": claim.cid,
                            "text": claim.text,
                            "frequency_score": sum(
                                judgment.score for judgment in judgments_by_cid[claim.cid]
                            ),
                            "support_count": sum(
                                judgment.score == 1 for judgment in judgments_by_cid[claim.cid]
                            ),
                            "comparison_count": len(comparisons),
                            "support_rate": sum(
                                judgment.score == 1 for judgment in judgments_by_cid[claim.cid]
                            )
                            / len(comparisons),
                        }
                        for claim in claims
                    ],
                }
            )

    output_dir = Path(output_dir)
    write_jsonl(output_dir / "ext_claims.jsonl", claim_rows)
    write_jsonl(output_dir / "ext_judgments.jsonl", judgment_rows)
    write_jsonl(output_dir / "ext_baseline_scores.jsonl", score_rows)
    write_jsonl(output_dir / "ext_h3_failures.jsonl", failures)
    return H3Summary(
        prompts=len(records),
        split_responses=len(claim_rows),
        target_rows=len(score_rows),
        failure_rows=len(failures),
    )


def build_fact_responses(
    score_rows: Sequence[Mapping],
    labels: Mapping[tuple[str, int, int], str],
) -> list[FactResponse]:
    """Join human labels to H3 scores for the shared conformal functions."""
    responses = []
    missing = []
    for row in score_rows:
        pid = str(row["pid"])
        target_id = int(row["target_response_id"])
        claims = []
        for raw_claim in row["claims"]:
            cid = int(raw_claim["cid"])
            key = (pid, target_id, cid)
            if key not in labels:
                missing.append(key)
                continue
            annotation = str(labels[key])
            if annotation not in VALID_ANNOTATIONS:
                raise ValueError(f"invalid label {annotation!r} for {key}")
            claims.append(
                FactClaim(
                    cid=cid,
                    text=str(raw_claim["text"]),
                    annotation=annotation,
                    score=float(raw_claim["frequency_score"]),
                    noise=0.0,
                )
            )
        if missing:
            continue
        responses.append(
            FactResponse(
                pid=f"{pid}-r{target_id}",
                prompt=str(row["prompt"]),
                claims=tuple(claims),
            )
        )
    if missing:
        raise ValueError(f"missing labels for {len(missing)} claims; first={missing[0]}")
    if not responses:
        raise ValueError("score rows produced no responses")
    return responses
