# Assembling the report

One page that says where every section of the final report already lives, what
backs its numbers, and what is still missing. The report is the four parts the
brief asks for; Part 5 is the optional research appendix.

## Where the sections are

| Report part | Draft | Length | Status |
|---|---|---|---|
| 1a, 2a, 3a — ConU on TriviaQA | [A-conu-sections.md](../docs/analysis/A-conu-sections.md) | 82 lines | reviewed against the repo in [A4-reproduction-review.md](../docs/analysis/A4-reproduction-review.md) and [A5-resampling-review.md](../docs/analysis/A5-resampling-review.md) |
| 1b, 2b, 3b — conformal factuality | [B-factuality-sections.md](B-factuality-sections.md) | 396 lines | reviewed in [B-report-review.md](../docs/analysis/B-report-review.md) |
| 1c — shared infrastructure | [C-infrastructure-sections.md](C-infrastructure-sections.md) | 104 lines | complete, all statements checkable from the repository |
| 4 — cross-response claim scoring | [C-extension.md](../docs/analysis/C-extension.md) | 189 lines | complete; every number comes from a committed result file, and the two label objections are now measured rather than deferred |
| 5 — evidence adjudication (bonus) | [part5-evidence-adjudication.md](part5-evidence-adjudication.md) | 231 lines | complete; research extension beyond the four required parts |

Supporting material that is not itself a section:

| Material | Where |
|---|---|
| Tables 1–3, with a regeneration recipe | [main-tables.md](../docs/analysis/main-tables.md) |
| Case studies | [A-conu-cases.md](../docs/analysis/A-conu-cases.md), [B-factuality-cases.md](../docs/analysis/B-factuality-cases.md) |
| Grids and sensitivity | [B-grid.md](../docs/analysis/B-grid.md), [A5-A-conu-grid-handoff.md](../docs/analysis/A5-A-conu-grid-handoff.md) |
| Handoffs between workstreams | [H3](../docs/analysis/H3-B-to-C-handoff.md), [H5](../docs/analysis/H5-B-results-handoff.md), [H7](../docs/analysis/H7-B-factuality-handoff.md) |
| Environment, versions, schemas, repro checklist | [docs/reference/](../docs/reference/) |

## Where the numbers come from

Every number in the drafts traces to a committed file. When assembling, take the
figures from the result files, not from the prose, and prefer
[main-tables.md](../docs/analysis/main-tables.md) for Tables 1–3.

| Component | Result files |
|---|---|
| ConU, two targets x three calibration sizes | `exp/results/conu__a*.json` (6 files) |
| Conformal factuality, two targets x three calibration sizes | `exp/results/fact__a*.json` (6 files) |
| Part 4, grounded and discarded labels | `exp/results/extension/{grounded,weak}/ext_*.json` (8 files) |
| A4 filter audit, A3 scalar export, resampling grid | `exp/handoff/a5_resampling/` |
| Part 5 adjudication runs and the B2 sensitivity | `exp/handoff/part5-pilot/` |

Each result file carries a `run_result` block: code commit, split hash, and a
`reportable` flag that is false when the work tree was dirty outside `exp/`.
Part 1c documents the convention.

## Figures

| Figure | File | Referenced by |
|---|---|---|
| ConU coverage versus retained answers | `figures/conu_a5_coverage_vs_size.png` | 3a |
| Retention versus factuality | `figures/retention_vs_factuality.png` / `.pdf` | 1b |
| Claim diagnostics | `figures/factuality_claim_diagnostics.png` / `.pdf` | 2b |
| Part 4 comparison | `figures/extension_comparison.png` / `.pdf` | 4 |

## What is missing before submission

1. **Contribution review.** A's statement is reviewed, B's statement is now
   written and awaiting review, and C's statement remains a draft. See
   [A.md](../docs/contributions/A.md), [B.md](../docs/contributions/B.md),
   [C.md](../docs/contributions/C.md), and the
   [evidence index](../docs/contributions/README.md).
2. **A single document.** The five drafts were written independently and do not
   share a numbering scheme, a notation for the conformal quantities, or a
   reference list. B's draft already carries `Limitations` and `References`;
   the assembled report should keep one of each, not five.

## What is deliberately not in the repository

The repository is public. Dataset text, model generations, the TriviaQA cache
used by A, and the `a4-evidence-*` / `cache/` directories are therefore absent.
Anything a reader needs in order to *check* a number is committed; anything
needed only in order to *re-run* a model is not.
