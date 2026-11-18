# Individual contribution statement — C

> AIAA 4051 Natural Language Processing, Fall 2026.
> Conformal Prediction for Reliable Short- and Long-Form Question Answering.

I was responsible for the shared infrastructure and for the Part 4 extension.

I built and maintained the shared package that both experiment lines run on: the
configuration scheme, the frozen splits, the `run_result` provenance stamp that
records the code commit and split hash in every result file, dependency pinning,
the CI checks, and the line-ending policy that keeps the archived teammate
deliverables byte-stable. I wrote Section 1c, which documents all of it,
including an explicit account of what can and cannot be reproduced from a clean
clone.

For Part 4 I implemented cross-response claim scoring — claims from the five
sampled responses are compared pairwise with the same cross-encoder the
short-form line uses, merged into clusters, and scored by the number of distinct
responses that agree — and evaluated it against the judge-frequency baseline
under an identical split-conformal rule and sampling budget. The first label set
turned out to be unreliable: I hand-checked seventeen of its labels against
Wikipedia and found six wrong, so I discarded it and relabelled the claims
against cached article extracts. The result is a negative finding, and I wrote it
up as one: consistency is a real but weak signal, and the two methods are
identical where it matters.

I reviewed the teammates' deliverables against the repository rather than
against their own summaries, and kept the audit records (A4, A5, and the Part B
report review), together with the corrections that came out of them. I also
drafted the Part 5 research extension: a blind evidence-adjudication protocol
with a fixed prompt and output schema, the pilot and 80-claim packages, two
independent model runs, and the validation records. When the data contradicted
the scoring rule I had written, I corrected the rule and recorded why.

---

## Backing in the repository

Not part of the statement above; kept here so each claim can be checked.

| Claim | Where it is visible |
|---|---|
| shared package, configs, CI, pinning | `.github/workflows/`, `configs/`, `pyproject.toml`, commit `7e2bebf` |
| provenance stamp in every result file | `src/confqa/common/`, documented in [C-infrastructure-sections.md](../../reports/C-infrastructure-sections.md) |
| frozen splits | `data/splits/triviaqa_a3.json`, `data/splits/factscore.json`, hashed into every `run_result` |
| Section 1c | [C-infrastructure-sections.md](../../reports/C-infrastructure-sections.md) |
| cross-response scoring and evaluation | `src/confqa/extension/{cluster,evaluate,relabel,report}.py` |
| label audit, 6 of 17 wrong | [C-extension.md](../analysis/C-extension.md), `exp/results/extension/{grounded,weak}/` |
| Part 4 as a negative result | [C-extension.md](../analysis/C-extension.md) |
| review records | [A4](../analysis/A4-reproduction-review.md), [A5](../analysis/A5-resampling-review.md), [B](../analysis/B-report-review.md) |
| Part 5 protocol and packages | `exp/handoff/part5-pilot/llm_adjudication/` |
| two independent model runs | `exp/handoff/part5-pilot/llm_adjudication/runs/` |
| correcting the scoring rule | [gpt6-luna_subset20 validation](../../exp/handoff/part5-pilot/llm_adjudication/runs/gpt6-luna_subset20_2026-11-17.validation.md) |
| threshold sensitivity | [B2-thresholds.md](../../exp/handoff/part5-pilot/hpc/B2-thresholds.md) |
