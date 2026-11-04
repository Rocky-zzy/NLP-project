"""Inspect successful and unsuccessful conformal-factuality cases."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from confqa.common.io import load_config

from .conformal import conformal_threshold, rank_score, retain_claims
from .data import (
    CORRECT_ANNOTATIONS,
    FactClaim,
    FactResponse,
    load_factscore_responses,
    load_factscore_split,
)
from .evaluate import (
    DEFAULT_CONFIG,
    _path_label,
    _resolve_path,
    select_calibration,
)


@dataclass(frozen=True)
class CaseClaim:
    """One claim with its final filtering decision."""

    cid: int
    text: str
    annotation: str
    score: float
    noise: float
    retained: bool

    @property
    def correct(self) -> bool:
        return self.annotation in CORRECT_ANNOTATIONS


@dataclass(frozen=True)
class CaseView:
    """A test response prepared for qualitative inspection."""

    pid: str
    prompt: str
    original_output: str | None
    claims: tuple[CaseClaim, ...]

    @property
    def retained(self) -> tuple[CaseClaim, ...]:
        return tuple(claim for claim in self.claims if claim.retained)

    @property
    def dropped(self) -> tuple[CaseClaim, ...]:
        return tuple(claim for claim in self.claims if not claim.retained)

    @property
    def empty(self) -> bool:
        return not self.retained

    @property
    def retained_all_correct(self) -> bool:
        return bool(self.retained) and all(claim.correct for claim in self.retained)

    @property
    def retained_incorrect(self) -> tuple[CaseClaim, ...]:
        return tuple(claim for claim in self.retained if not claim.correct)

    @property
    def retention(self) -> float:
        return len(self.retained) / len(self.claims) if self.claims else float("nan")


def load_survey_outputs(
    path: str | Path,
    *,
    response_count: int,
) -> dict[str, tuple[str, str]]:
    """Recover original and upstream-filtered outputs from the final 30 prompts."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = data.get("data") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise ValueError("survey must contain a data array")
    if len(rows) > response_count:
        raise ValueError("survey has more rows than the response dataset")

    start = response_count - len(rows)
    outputs = {}
    for offset, row in enumerate(rows):
        pid = f"factscore-{start + offset:04d}"
        option = str(row.get("C-factal option"))
        answer_1 = row.get("Answer 1")
        answer_2 = row.get("Answer 2")
        if not isinstance(answer_1, str) or not isinstance(answer_2, str):
            raise ValueError(f"{pid} has a missing survey answer")
        if option == "1":
            original, filtered = answer_2, answer_1
        else:
            original, filtered = answer_1, answer_2
        outputs[pid] = (original, filtered)
    return outputs


def build_case_views(
    responses: list[FactResponse],
    threshold: float,
    survey_outputs: dict[str, tuple[str, str]],
) -> list[CaseView]:
    """Attach filtering decisions and optional original text to responses."""
    views = []
    for response in responses:
        kept_ids = {claim.cid for claim in retain_claims(response.claims, threshold)}
        survey = survey_outputs.get(response.pid)
        views.append(
            CaseView(
                pid=response.pid,
                prompt=response.prompt,
                original_output=survey[0] if survey else None,
                claims=tuple(
                    _case_claim(claim, claim.cid in kept_ids) for claim in response.claims
                ),
            )
        )
    return views


def _case_claim(claim: FactClaim, retained: bool) -> CaseClaim:
    return CaseClaim(
        cid=claim.cid,
        text=claim.text,
        annotation=claim.annotation,
        score=claim.score,
        noise=claim.noise,
        retained=retained,
    )


def summarize_case_views(cases: list[CaseView]) -> dict:
    """Count mutually exclusive outcomes and original-output availability."""
    return {
        "n_test": len(cases),
        "n_empty": sum(case.empty for case in cases),
        "n_all_correct_nonempty": sum(case.retained_all_correct for case in cases),
        "n_retained_incorrect": sum(bool(case.retained_incorrect) for case in cases),
        "n_original_available": sum(case.original_output is not None for case in cases),
    }


def _wrapped_rows(path: str | Path) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = data.get("data") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise ValueError(f"{path} must contain a data array")
    return rows


def audit_cached_exclusions(
    responses: list[FactResponse],
    merged_path: str | Path,
) -> dict:
    """Report exclusions observable in the shipped caches."""
    merged = _wrapped_rows(merged_path)
    return {
        "n_responses": len(responses),
        "n_empty_claim_sets": sum(not response.claims for response in responses),
        "n_merged_responses": len(merged),
        "n_missing_merged_responses": max(0, len(responses) - len(merged)),
        "n_missing_accepted_claims": sum("accepted-subclaims" not in row for row in merged),
        "n_empty_accepted_claims": sum(not row.get("accepted-subclaims") for row in merged),
        "n_missing_new_output": sum("new-output" not in row for row in merged),
        "n_empty_new_output": sum(not row.get("new-output") for row in merged),
        "n_abstain_outputs": sum(row.get("new-output") == "Abstain." for row in merged),
        "n_parse_failures": None,
    }


def analyze_primary_cases(config_path: str | Path = DEFAULT_CONFIG) -> dict:
    """Build case views and summaries for the configured primary condition."""
    path = _resolve_path(config_path)
    document = load_config(path)
    settings = document["factuality"]
    scored_path = _resolve_path(settings["scored_path"])
    split_path = _resolve_path(settings["split_path"])
    survey_path = _resolve_path(settings["survey_path"])
    merged_path = _resolve_path(settings["merged_path"])

    responses = load_factscore_responses(
        scored_path,
        score_field=settings["score_field"],
    )
    splits = load_factscore_split(responses, split_path)
    calibration = select_calibration(
        splits["calib_pool"],
        float(settings["case_calib_frac"]),
        seed=int(document["seed"]),
    )
    threshold = conformal_threshold(
        [rank_score(response.claims) for response in calibration],
        float(settings["case_alpha"]),
    )
    survey_outputs = load_survey_outputs(
        survey_path,
        response_count=len(responses),
    )
    cases = build_case_views(splits["test"], threshold, survey_outputs)

    return {
        "config": _path_label(path),
        "alpha": float(settings["case_alpha"]),
        "calib_frac": float(settings["case_calib_frac"]),
        "n_calibration": len(calibration),
        "threshold": threshold,
        "summary": summarize_case_views(cases),
        "cache_audit": audit_cached_exclusions(responses, merged_path),
        "cases": cases,
    }
