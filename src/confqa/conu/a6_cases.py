"""Export the ConU A6 examples from the frozen TriviaQA test split."""

from __future__ import annotations

import json

from confqa.common.paths import REPO_ROOT
from confqa.common.results import file_sha256
from confqa.conu.a5_grid import A3, CONFIG, load_inputs

CASE_SPECS = (
    (
        "dpql_825",
        "Success",
        "Correct name survives an incorrect first sample",
        "The first sample names Sarah Lancashire. Slot 3 names the benchmark answer, "
        "Nicola Walker, and is retained in the 12-slot prediction set.",
    ),
    (
        "qw_3850",
        "Success",
        "The set preserves a correct location",
        "The first sample gives Dublin, Ireland. Slot 5 gives Cardiff, Wales, which "
        "matches the benchmark location and is retained in the 15-slot set.",
    ),
    (
        "odql_4634",
        "Failure",
        "Repeated sampling supplies no acceptable candidate",
        "All 20 cleaned answers say Perth, Scotland, while the benchmark answer is "
        "Edinburgh. All 20 slots survive the cutoff, and every slot falls below the "
        "acceptability threshold.",
    ),
    (
        "bt_3134",
        "Failure",
        "The only acceptable candidate is filtered out",
        "Slot 3 supplies Mars, the benchmark answer. Its gold similarity is 0.750, "
        "but its nonconformity is 0.997, above the 0.95 cutoff. The 18 retained "
        "slots contain zero acceptable candidates.",
    ),
)


def load_selected(path, qids):
    with path.open(encoding="utf-8") as handle:
        return {row["qid"]: row for row in map(json.loads, handle) if row["qid"] in qids}


def build_cases(root):
    config = json.loads((root / CONFIG).read_bytes())
    _, test, a4, source_hashes = load_inputs(root, config)
    test_by_id = {row["qid"]: row for row in test}
    grid_files = sorted((root / "exp/results").glob("conu__*.json"))
    grid = [json.loads(path.read_bytes()) for path in grid_files]
    if len(grid) != 6 or {row["threshold"] for row in grid} != {0.95}:
        raise ValueError("A6 expects the six verified A5 configurations with cutoff 0.95.")
    if any(row["input_sha256"] != source_hashes for row in grid):
        raise ValueError("The A5 grid and A6 source files differ.")
    q_hat = grid[0]["threshold"]
    correctness = config["correctness_threshold"]
    qids = {item[0] for item in CASE_SPECS} | {"qw_4781"}
    source = root / A3
    scoring_plan_path = source / "similarity/plan.json"
    if file_sha256(scoring_plan_path) != a4["a3_input_sha256"]["similarity/plan.json"]:
        raise ValueError("The saved A3 scoring plan changed.")
    scoring_plan = json.loads(scoring_plan_path.read_bytes())
    expected_hashes = {
        "conu_generations.jsonl": scoring_plan["raw_sha256"],
        "conu_generations.cleaned.jsonl": scoring_plan["cleaned_sha256"],
        "similarity/scores.jsonl": a4["a3_input_sha256"]["similarity/scores.jsonl"],
    }
    for name, expected in expected_hashes.items():
        digest = file_sha256(source / name)
        if digest != expected:
            raise ValueError(f"A3 data changed: {name}")
        source_hashes[(A3 / name).as_posix()] = digest
    source_hashes[(A3 / "similarity/plan.json").as_posix()] = file_sha256(scoring_plan_path)
    raw, cleaned, scored = (load_selected(source / name, qids) for name in expected_hashes)

    def evidence(qid):
        row = test_by_id[qid]
        generation, clean, score = raw[qid], cleaned[qid], scored[qid]
        if (
            generation["samples"] != clean["samples_raw"]
            or clean["samples"] != score["samples"]
            or score["samples"] != row["samples"]
            or score["similarity_to_canonical_gold"] != row["gold_similarity"]
            or generation["gold_value"] != row["canonical_gold"]
            or generation["question"] != row["question"]
        ):
            raise ValueError(f"Mismatched per-slot evidence for {qid}.")
        slots = [
            {
                "slot": number,
                "raw_answer": original,
                "cleaned_answer": text,
                "gold_similarity": similarity,
                "nonconformity": nc,
                "acceptable": similarity >= correctness,
                "retained": nc <= q_hat,
            }
            for number, (original, text, similarity, nc) in enumerate(
                zip(
                    generation["samples"],
                    row["samples"],
                    row["gold_similarity"],
                    row["sample_nonconformity"],
                    strict=True,
                ),
                start=1,
            )
        ]
        retained = [slot for slot in slots if slot["retained"]]
        covered = any(slot["acceptable"] for slot in retained)
        for alpha in config["alphas"]:
            expected = row["prediction_sets"][str(alpha)]
            if (
                expected["indices"] != [slot["slot"] - 1 for slot in retained]
                or expected["answers"] != [slot["cleaned_answer"] for slot in retained]
                or expected["covered"] != covered
            ):
                raise ValueError(f"A6 disagrees with the saved A3 answer set for {qid}.")
        return {
            "qid": qid,
            "question": row["question"],
            "canonical_gold": row["canonical_gold"],
            "gold_aliases": generation["gold"],
            "covered_by_similarity_rule": covered,
            "n_acceptable": sum(slot["acceptable"] for slot in slots),
            "prediction_set": [
                {"slot": slot["slot"], "answer": slot["cleaned_answer"]} for slot in retained
            ],
            "slots": slots,
        }

    cases = []
    for qid, label, title, interpretation in CASE_SPECS:
        case = evidence(qid)
        if case["covered_by_similarity_rule"] != (label == "Success"):
            raise ValueError(f"Unexpected outcome for {qid}.")
        cases.append({**case, "outcome": label, "title": title, "interpretation": interpretation})
    proxy = evidence("qw_4781")
    proxy_hits = [slot for slot in proxy["slots"] if slot["retained"] and slot["acceptable"]]
    if [slot["slot"] for slot in proxy_hits] != [8, 19]:
        raise ValueError("The similarity false-positive example changed.")
    return {
        "schema": "confqa.conu.a6_cases.v1",
        "test_questions": len(test),
        "alphas": config["alphas"],
        "q_hat": q_hat,
        "correctness_threshold": correctness,
        "test_without_acceptable_candidate": sum(not row["has_acceptable_sample"] for row in test),
        "test_with_acceptable_candidate_but_uncovered": sum(
            row["has_acceptable_sample"] and not row["prediction_sets"]["0.1"]["covered"]
            for row in test
        ),
        "input_sha256": {
            **source_hashes,
            **{path.relative_to(root).as_posix(): file_sha256(path) for path in grid_files},
        },
        "selection": "Post hoc illustrative examples from the fixed held-out test set.",
        "cases": cases,
        "similarity_proxy_check": {
            "qid": proxy["qid"],
            "question": proxy["question"],
            "canonical_gold": proxy["canonical_gold"],
            "threshold_passes": proxy_hits,
        },
    }


def render_markdown(data):
    lines = [
        "# ConU short-answer case studies",
        "",
        "Four illustrative cases from the fixed 250-question TriviaQA test split. "
        "The answers are cached generations from the team’s Qwen2.5-14B-Instruct run.",
        "",
        f"ConU retains slots with nonconformity at or below {data['q_hat']:.2f} in both α settings. "
        f"Gold similarity is scored on the cleaned answer and passes at {data['correctness_threshold']:.2f}. "
        "Repeated texts count as separate slots. The examples were selected after evaluation to illustrate mechanisms.",
        "",
        f"Across the test set, {data['test_without_acceptable_candidate']} questions had zero acceptable candidates. "
        f"Another {data['test_with_acceptable_candidate_but_uncovered']} had an acceptable candidate "
        "and lost every acceptable candidate at the cutoff.",
        "",
        "| Outcome | Question ID | Acceptable candidates out of 20 | Retained slots |",
        "|---|---|---:|---:|",
    ]
    for case in data["cases"]:
        lines.append(
            f"| {case['outcome']} | `{case['qid']}` | {case['n_acceptable']} | "
            f"{len(case['prediction_set'])} |"
        )
    for case in data["cases"]:
        slots = ", ".join(str(slot["slot"]) for slot in case["prediction_set"])
        lines += [
            "",
            f"## {case['title']} (`{case['qid']}`)",
            "",
            f"**Question** {case['question']}",
            "",
            f"**Benchmark answer** {case['canonical_gold']}",
            "",
            case["interpretation"],
            "",
            f"**Prediction set** Slots {slots}. Their cleaned answer texts appear in the table.",
            "",
            "| Slot | Gold similarity | Nonconformity | Passes similarity | In prediction set | Cleaned answer |",
            "|---:|---:|---:|:---:|:---:|---|",
        ]
        for slot in case["slots"]:
            answer = (
                slot["cleaned_answer"]
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("|", "&#124;")
                .replace("\n", " ")
            )
            passes = "Yes" if slot["acceptable"] else "No"
            retained = "Yes" if slot["retained"] else "No"
            lines.append(
                f"| {slot['slot']} | {slot['gold_similarity']:.5f} | {slot['nonconformity']:.5f} | "
                f"{passes} | {retained} | {answer} |"
            )
        lines += [
            "",
            "<details>",
            "<summary>All 20 original model outputs in slot order</summary>",
            "",
            "```json",
            json.dumps(
                [slot["raw_answer"] for slot in case["slots"]], ensure_ascii=False, indent=2
            ),
            "```",
            "",
            "</details>",
        ]
    proxy = data["similarity_proxy_check"]
    hit = proxy["threshold_passes"][0]
    lines += [
        "",
        "## Similarity-based correctness can overcount coverage",
        "",
        f"On `{proxy['qid']}`, the benchmark answer is {proxy['canonical_gold']}. "
        f"The two retained threshold passes (slots 8 and 19) both read “{hit['cleaned_answer']}” "
        f"and have gold similarity {hit['gold_similarity']:.5f}. The recorded coverage flag "
        "is therefore a false positive under a direct reading of the retained text. "
        "This case illustrates the limits of a similarity-based acceptability rule.",
        "",
    ]
    return "\n".join(lines)


def main():
    data = build_cases(REPO_ROOT)
    paths = {
        REPO_ROOT / "docs/analysis/A-conu-cases.md": render_markdown(data),
        REPO_ROOT / "cache/a6_cases/cases.json": json.dumps(data, ensure_ascii=False, indent=2)
        + "\n",
    }
    for path, content in paths.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        print(path)


if __name__ == "__main__":
    main()
