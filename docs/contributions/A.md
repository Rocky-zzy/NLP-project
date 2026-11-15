# Individual contribution statement — A

> AIAA 4051 Natural Language Processing, Fall 2026.
> Conformal Prediction for Reliable Short- and Long-Form Question Answering.

I was responsible for the ConU short-answer question answering component. I set
up and verified the Qwen2.5-14B-Instruct inference environment on the university
HPC platform, ran the full ConU pipeline on 100 TriviaQA questions, and scaled
the experiment to 500 questions with 20 responses each. I fixed the calibration
and test splits before generation and reused the generated responses for the
subsequent analyses.

I audited ConU's eligibility filter by comparing filtered and unfiltered
calibration and evaluation on the same underlying split. I evaluated two coverage
targets across three calibration sizes, computed bootstrap intervals for coverage
and answer-set size, and ran a seeded resampling analysis to assess sensitivity to
calibration subset selection. I documented two success cases and two failure
cases, drafted Sections 1a, 2a, and 3a, and shared the results, figures, and CPU
reproduction package with the team.

---

## Backing in the repository

Not part of the statement above; kept here so each claim can be checked.

| Claim | Where it is visible |
|---|---|
| inference environment, 100 then 500 questions | `configs/conu_a5.json`, `exp/handoff/a5_resampling/results/summary.json` |
| split fixed before generation | `selection_uses_model_outcomes: false`, `selection_seed: 0` in the frozen A3 split |
| responses reused for later analyses | A4 and the whole A5 grid run on CPU from one cached score matrix |
| eligibility-filter audit | `exp/handoff/a5_resampling/cache/a4_filter_audit/summary.json`, reviewed in [A4-reproduction-review.md](../analysis/A4-reproduction-review.md) |
| two targets x three calibration sizes, bootstrap intervals | `exp/results/conu__a*.json`, `figures/conu_a5_coverage_vs_size.png` |
| seeded resampling | `exp/handoff/a5_resampling/`, reviewed in [A5-resampling-review.md](../analysis/A5-resampling-review.md) |
| two success, two failure cases | [A-conu-cases.md](../analysis/A-conu-cases.md) |
| Sections 1a, 2a, 3a | [A-conu-sections.md](../analysis/A-conu-sections.md) |
| CPU reproduction package | archived outside git at `a4-evidence-20261113/` (contains dataset text and model outputs, so it is not public) |
