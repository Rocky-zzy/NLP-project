"""Load and validate the cached FActScore inputs."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from confqa.common.paths import DATA, REPO_ROOT

UPSTREAM = REPO_ROOT / "third_party" / "conformal-factual-lm"
DEFAULT_SCORED_PATH = UPSTREAM / "out" / "factscore_subclaims_with_scores.jsonl"
DEFAULT_SPLIT_PATH = DATA / "splits" / "factscore.json"

VALID_ANNOTATIONS = frozenset({"Y", "S", "N", "U"})
CORRECT_ANNOTATIONS = frozenset({"Y", "S"})


@dataclass(frozen=True)
class FactClaim:
    """One cached claim and its upstream scores."""

    cid: int
    text: str
    annotation: str
    score: float
    noise: float

    @property
    def correct(self) -> bool:
        return self.annotation in CORRECT_ANNOTATIONS


@dataclass(frozen=True)
class FactResponse:
    """One FActScore prompt with its ordered cached claims."""

    pid: str
    prompt: str
    claims: tuple[FactClaim, ...]


def _load_data_array(path: str | Path) -> list[dict[str, Any]]:
    """Read the wrapped JSON used by the upstream repository."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        records = data.get("data")
    else:
        records = data
    if not isinstance(records, list):
        raise ValueError(f"{path} must contain a top-level data array")
    return records


def load_factscore_responses(
    path: str | Path = DEFAULT_SCORED_PATH,
    *,
    score_field: str = "frequency-score",
) -> list[FactResponse]:
    """Load FActScore responses using positional factscore-0000 ids."""
    responses: list[FactResponse] = []
    seen_ids: set[str] = set()

    for row_index, record in enumerate(_load_data_array(path)):
        pid = f"factscore-{row_index:04d}"
        if pid in seen_ids:
            raise ValueError(f"duplicate response id: {pid}")
        seen_ids.add(pid)

        prompt = record.get("prompt")
        raw_claims = record.get("claims")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError(f"{pid} has no non-empty prompt")
        if not isinstance(raw_claims, list):
            raise ValueError(f"{pid} has no claims array")

        claims: list[FactClaim] = []
        for claim_index, raw_claim in enumerate(raw_claims):
            label = f"{pid} claim {claim_index}"
            text = raw_claim.get("subclaim")
            annotation = raw_claim.get("annotation")
            if not isinstance(text, str) or not text.strip():
                raise ValueError(f"{label} has no non-empty text")
            if annotation not in VALID_ANNOTATIONS:
                raise ValueError(f"{label} has invalid annotation {annotation!r}")
            for field in (score_field, "noise"):
                if field not in raw_claim:
                    raise ValueError(f"{label} is missing {field}")

            try:
                score = float(raw_claim[score_field])
                noise = float(raw_claim["noise"])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{label} has a non-numeric score") from exc
            if not score == score or not noise == noise:
                raise ValueError(f"{label} has a NaN score")

            claims.append(
                FactClaim(
                    cid=claim_index,
                    text=text,
                    annotation=annotation,
                    score=score,
                    noise=noise,
                )
            )

        responses.append(FactResponse(pid=pid, prompt=prompt, claims=tuple(claims)))

    return responses


def load_factscore_split(
    responses: list[FactResponse],
    path: str | Path = DEFAULT_SPLIT_PATH,
) -> dict[str, tuple[FactResponse, ...]]:
    """Join a fixed split manifest to responses and reject leakage."""
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    split_ids = document.get("splits")
    if not isinstance(split_ids, dict):
        raise ValueError(f"{path} has no splits object")

    by_id = {response.pid: response for response in responses}
    if len(by_id) != len(responses):
        raise ValueError("response ids are not unique")

    flat_ids = [str(pid) for ids in split_ids.values() for pid in ids]
    if len(flat_ids) != len(set(flat_ids)):
        raise ValueError("split ids overlap")

    expected = set(by_id)
    actual = set(flat_ids)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise ValueError(f"split mismatch: missing={missing}, unknown={unknown}")

    return {name: tuple(by_id[str(pid)] for pid in ids) for name, ids in split_ids.items()}


def annotation_counts(responses: list[FactResponse]) -> dict[str, int]:
    """Count claim annotations for input validation and reporting."""
    counts = Counter(claim.annotation for response in responses for claim in response.claims)
    return dict(sorted(counts.items()))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate cached FActScore inputs.")
    parser.add_argument("--scored", default=str(DEFAULT_SCORED_PATH))
    parser.add_argument("--split", default=str(DEFAULT_SPLIT_PATH))
    parser.add_argument("--score-field", default="frequency-score")
    args = parser.parse_args(argv)

    responses = load_factscore_responses(args.scored, score_field=args.score_field)
    splits = load_factscore_split(responses, args.split)
    print(f"responses={len(responses)}")
    print(f"claims={sum(len(response.claims) for response in responses)}")
    print(f"annotations={annotation_counts(responses)}")
    print(f"splits={{{', '.join(f'{name}: {len(items)}' for name, items in splits.items())}}}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
