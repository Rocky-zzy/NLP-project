#!/usr/bin/env python3
"""Prepare a small, reproducible TriviaQA input set; never load an LLM."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import random
import subprocess
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

SOURCE_REVISION = "0f7faf33a3908546c6fd5b73a660e0f8ff173c2f"
SOURCE_SHA256 = "48a5005c0eb4f8a4ae5b9868644297fd5bf1e694aeb3dc9c8ab958cac0d5b201"
UPSTREAM_REVISION = "c0c450e8dbef489cfed28f585f1a4ddf0e66078b"
SELECTION_SEED = 0
FEW_SHOT_SEED = 10  # Preserve the original parse_triviaqa.py example-row draw.
N_QUESTIONS = 50
N_CALIBRATION = 25
N_FEW_SHOT = 3


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def question_key(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def json_bytes(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def jsonl_bytes(records: list[dict]) -> bytes:
    return "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in records).encode("utf-8")


def strings(values) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        raise ValueError("Expected a list of aliases, got a string.")
    result = list(values)
    if any(not isinstance(s, str) for s in result):
        raise ValueError("An alias is not a string.")
    return result


def deduplicate(rows: list[dict]) -> tuple[list[dict], dict]:
    groups = defaultdict(list)
    for index, row in enumerate(rows):
        qid, text, answer = row["question_id"], row["question"], row["answer"]
        if not isinstance(qid, str) or not qid.strip():
            raise ValueError(f"Missing/invalid question ID at raw row {index}.")
        if not isinstance(text, str) or not isinstance(answer, dict):
            raise ValueError(f"Invalid question or answer at raw row {index}.")
        value = answer.get("value")
        if not isinstance(value, str):
            raise ValueError(f"Invalid answer.value at raw row {index}.")
        groups[qid].append({
            "raw_row_index": index,
            "question": text,
            "answer_value": value,
            "aliases": strings(answer.get("aliases")),
            "normalized_aliases": strings(answer.get("normalized_aliases")),
        })

    unique = []
    excluded = []
    for qid, members in sorted(groups.items()):
        texts = sorted({r["question"] for r in members})
        values = sorted({r["answer_value"] for r in members})
        reasons = []
        if len(texts) != 1:
            reasons.append("different_question_texts_for_same_id")
        if len(values) != 1:
            reasons.append("different_canonical_answers_for_same_id")
        if any(not s.strip() for s in texts + values):
            reasons.append("empty_question_or_canonical_answer")
        if reasons:
            excluded.append({"qid": qid, "reasons": reasons, "raw_records": members})
            continue
        gold = {r["answer_value"] for r in members}
        gold.update(a for r in members for a in r["aliases"] if a.strip())
        normalized_aliases = {a for r in members for a in r["normalized_aliases"] if a.strip()}
        unique.append({
            "qid": qid,
            "question": texts[0],
            "gold_value": values[0],
            "gold": [values[0]] + sorted(gold - {values[0]}),
            "normalized_aliases": sorted(normalized_aliases),
            "source_row_indices": [r["raw_row_index"] for r in members],
        })

    # Detect equivalent text under distinct IDs, without changing question wording.
    text_groups = defaultdict(list)
    for record in unique:
        text_groups[question_key(record["question"])].append(record["qid"])
    collisions = [sorted(ids) for _, ids in sorted(text_groups.items()) if len(ids) > 1]
    collision_ids = {qid for ids in collisions for qid in ids}
    audit = {
        "raw_rows": len(rows),
        "unique_source_ids": len(groups),
        "duplicate_id_rows": len(rows) - len(groups),
        "unique_consistent_ids": len(unique),
        "excluded_source_conflicts": excluded,
        "normalized_text_collisions_between_ids": collisions,
        "selection_excludes_normalized_collision_ids": sorted(collision_ids),
        "note": "Source-quality checks only. No model answers or correctness scores are used.",
    }
    return unique, audit


def make_plan(unique: list[dict], few_shot_ids: list[str], collision_ids: set[str],
              count: int = N_QUESTIONS, calibration_count: int = N_CALIBRATION) -> tuple[list[dict], list[dict], dict]:
    if not 2 <= count <= 50 or not 1 <= calibration_count < count:
        raise ValueError("Pilot must have 2..50 questions and nonempty disjoint splits.")
    by_id = {r["qid"]: r for r in unique}
    if len(few_shot_ids) != N_FEW_SHOT or len(set(few_shot_ids)) != N_FEW_SHOT:
        raise ValueError("The upstream few-shot row draw did not yield three distinct IDs.")
    for qid in few_shot_ids:
        if qid not in by_id or qid in collision_ids:
            raise ValueError(f"Few-shot ID {qid} has a source conflict; no silent replacement.")
        if not by_id[qid]["question"].isascii() or not by_id[qid]["gold_value"].isascii():
            raise ValueError(f"Few-shot ID {qid} fails the upstream ASCII condition.")
    demos = [by_id[qid] for qid in few_shot_ids]
    demo_keys = {question_key(r["question"]) for r in demos}
    eligible = [r for r in sorted(unique, key=lambda r: r["qid"])
                if r["qid"] not in set(few_shot_ids)
                and r["qid"] not in collision_ids
                and question_key(r["question"]) not in demo_keys
                and r["question"].isascii() and r["gold_value"].isascii()]
    if len(eligible) < count:
        raise ValueError(f"Only {len(eligible)} eligible questions; need {count}.")
    random.Random(SELECTION_SEED).shuffle(eligible)
    selected = eligible[:count]
    qids = [r["qid"] for r in selected]
    split = {
        "schema": "confqa.triviaqa.a2_pilot.v1",
        "selection_seed": SELECTION_SEED,
        "few_shot_seed": FEW_SHOT_SEED,
        "few_shot_ids": few_shot_ids,
        "calibration_ids": qids[:calibration_count],
        "test_ids": qids[calibration_count:],
        "generation_order": qids,
        "eligible_unique_questions_after_exclusions": len(eligible),
        "no_performance_based_selection": True,
        "scope": "Small pipeline pilot; cached main reproduction remains a separate data-source question.",
    }
    assert not set(split["calibration_ids"]) & set(split["test_ids"])
    assert not set(qids) & set(few_shot_ids)
    assert len({question_key(r["question"]) for r in selected + demos}) == count + N_FEW_SHOT
    return selected, demos, split


def git_head(path: Path) -> str:
    return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()


def write_outputs(project: Path, outputs: dict[str, bytes]) -> None:
    # Preflight all paths before any write; reruns may reuse identical artifacts.
    for relative, data in outputs.items():
        path = project / relative
        if path.is_symlink() or (path.exists() and (not path.is_file() or path.read_bytes() != data)):
            raise ValueError(f"Refusing to overwrite a different existing artifact: {relative}")
    for relative, data in outputs.items():
        path = project / relative
        if path.exists():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as handle:
            handle.write(data)


def main() -> None:
    import pandas as pd

    project = Path(__file__).resolve().parent
    if not (project / "pyproject.toml").is_file():
        raise ValueError("Upload a2_data.py into the NLP-project root directory, then run it there.")
    upstream_head = git_head(project / "third_party/ConU")
    if upstream_head != UPSTREAM_REVISION:
        raise ValueError(f"Unexpected ConU commit: {upstream_head}")
    source_relative = "data/raw/triviaqa/validation-00000-of-00001.parquet"
    source = project / source_relative
    source_hash = sha256(source.read_bytes())
    if source_hash != SOURCE_SHA256:
        raise ValueError(f"Raw file SHA256 mismatch: {source_hash}")
    rows = pd.read_parquet(source).to_dict(orient="records")
    unique, audit = deduplicate(rows)
    drawn_indices = random.Random(FEW_SHOT_SEED).sample(range(len(rows)), N_FEW_SHOT)
    few_shot_ids = [rows[i]["question_id"] for i in drawn_indices]
    collision_ids = set(audit["selection_excludes_normalized_collision_ids"])
    selected, demos, split = make_plan(unique, few_shot_ids, collision_ids)
    split["few_shot_raw_row_indices"] = drawn_indices
    prefix = "data/processed/triviaqa_a2"
    outputs = {
        f"{prefix}/unique_questions.jsonl": jsonl_bytes(unique),
        f"{prefix}/questions.jsonl": jsonl_bytes(selected),
        f"{prefix}/few_shot.jsonl": jsonl_bytes(demos),
        f"{prefix}/source_audit.json": json_bytes(audit),
        "data/splits/triviaqa_a2_pilot.json": json_bytes(split),
    }
    versions = {name: importlib.metadata.version(name)
                for name in ["pandas", "pyarrow", "torch", "transformers", "datasets"]}
    lock = project.parent / "logs/a2-requirements-lock.txt"
    manifest = {
        "schema": "confqa.triviaqa.a2_preparation.v1",
        "source": {"repo": "mandarjoshi/trivia_qa", "config": "rc.nocontext",
                   "split": "validation", "revision": SOURCE_REVISION,
                   "relative_path": source_relative, "sha256": source_hash,
                   "bytes": source.stat().st_size},
        "team_git_head": git_head(project),
        "conu_git_head": upstream_head,
        "preparation_script_sha256": sha256(Path(__file__).read_bytes()),
        "python": sys.version.split()[0],
        "packages": versions,
        "requirements_lock_sha256": sha256(lock.read_bytes()) if lock.is_file() else None,
        "raw_rows": len(rows),
        "unique_source_ids": audit["unique_source_ids"],
        "unique_consistent_ids": len(unique),
        "excluded_conflict_ids": [r["qid"] for r in audit["excluded_source_conflicts"]],
        "few_shot_questions": len(demos),
        "pilot_questions": len(selected),
        "calibration_questions": len(split["calibration_ids"]),
        "test_questions": len(split["test_ids"]),
        "supplementary_generation_cap": {"prompts": 50, "responses_per_prompt": 5},
        "actual_model_generation_requests": 0,
        "adaptations": [
            "One item per source question ID; merge original answer aliases.",
            "Quarantine source IDs with different question texts or canonical answers; retain audit records.",
            "Exclude cross-ID normalized-text collisions from the pilot and preserve the collision list.",
            "Keep upstream seed-10 few-shot row draw and exclude those IDs from evaluation.",
            "Use upstream ASCII condition for pilot question and canonical answer; retain all gold aliases.",
            "Sort candidate IDs then shuffle with seed 0; fix 50 pilot questions and a 25/25 split before generation.",
            "CPU data preparation only: no tokenizer/LLM load, no prompt generation, no model answer filtering.",
        ],
        "artifacts": {name: {"sha256": sha256(data), "bytes": len(data)} for name, data in outputs.items()},
    }
    outputs[f"{prefix}/manifest.json"] = json_bytes(manifest)
    write_outputs(project, outputs)
    print("A2 DATA READY")
    print(f"Raw rows: {len(rows)}; unique source IDs: {audit['unique_source_ids']}")
    print(f"Consistent unique questions: {len(unique)}")
    print("Quarantined source IDs:", manifest["excluded_conflict_ids"])
    print(f"Few-shot: {len(demos)}; pilot: {len(selected)}; calibration: {N_CALIBRATION}; test: {N_QUESTIONS - N_CALIBRATION}")
    print(f"Inputs: {prefix}/questions.jsonl")
    print("Splits: data/splits/triviaqa_a2_pilot.json")
    print("No model has been loaded or queried.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        raise SystemExit(f"ERROR: {exc}") from exc
