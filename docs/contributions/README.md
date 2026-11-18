# Contribution statements

Each statement is one short first-person paragraph plus a **Backing in the
repository** table, so a reader can check every claim without taking it on
trust. [A.md](A.md) is the model to follow.

| Person | Area | Statement |
|---|---|---|
| A | ConU, short-form QA | [A.md](A.md) — written and reviewed |
| B | conformal factuality, long-form | [B.md](B.md) — written, pending review |
| C | infrastructure, Part 4, Part 5 | [C.md](C.md) — draft, C to confirm |

The report needs all three before submission; see
[reports/README.md](../../reports/README.md).

## Evidence the statements have to agree with

The repository history is the first thing a reader will check, so a statement
should not contradict it.

- 62 commits, 2026-10-29 to 2026-11-18.
- 50 by `Rocky-zzy <zzy893310@outlook.com>`, 12 by
  `Gxl-creater <zgao260@connect.hkust-gz.edu.cn>`.

| Area | Primary paths | Commits |
|---|---|---|
| factuality line | `src/confqa/factuality/`, `configs/factuality.yaml`, `tests/test_factuality_*`, `reports/B-factuality-sections.md`, `exp/results/fact__*`, `figures/retention_vs_factuality.*` | `Gxl-creater` |
| ConU line | `src/confqa/conu/`, `configs/conu_a5.json`, `exp/results/conu__*`, `docs/analysis/A-*`, `exp/handoff/a5_resampling/` | delivered off-git by A, committed by C |
| shared package | `src/confqa/common/`, `pyproject.toml`, `.github/workflows/ci.yml`, `.gitattributes`, `Makefile` | `Rocky-zzy` |
| Part 4 extension | `src/confqa/extension/`, `tests/test_extension_report.py`, `exp/results/extension/`, `figures/extension_comparison.*` | `Rocky-zzy` |
| Part 5 research | `exp/handoff/part5-pilot/` | `Rocky-zzy` |

### The caveat that matters

**Commit authorship understates A's contribution and overstates C's.** A ran the
ConU experiments on the cluster and delivered sections, result files and a CPU
reproduction package outside git; those were committed from C's account so the
history stays linear. Anyone reading `git log` alone would credit the ConU line
to C.

The evidence that separates the two is in the repository itself: the
`exp/handoff/a5_resampling/` package, the `a4-evidence-20261113/` archive
reference, [A-conu-sections.md](../analysis/A-conu-sections.md),
[A.md](A.md), and the review records in [docs/analysis/](../analysis/).

A statement should therefore describe what a person did, and the backing table
should point at the artefact — not at a commit hash alone.
