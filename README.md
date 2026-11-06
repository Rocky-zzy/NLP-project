# NLP-project

Conformal Prediction for Reliable Short- and Long-Form Question Answering.

Course project for **AIAA 4051 Natural Language Processing (Fall 2026)**.
Three people, one inference model, a 20 GPU-hour budget, submit by 2026-11-30.

Large language models answer confidently and sometimes wrongly. This project
reproduces two conformal methods — **ConU** (prediction sets that cover a
correct answer) and **conformal factuality** (claim filtering that keeps the
retained content correct) — compares what "reliable" means in each, and tests
one small extension that carries ConU's cross-sample agreement signal into
claim scoring.

## Who does what

| Person | Scope | Code | Manual |
|---|---|---|---|
| **A** | ConU, short-form QA | `src/confqa/conu/` | [docs/manuals/A-conu.md](docs/manuals/A-conu.md) |
| **B** | Conformal factuality, long-form | `src/confqa/factuality/` | [docs/manuals/B-factuality.md](docs/manuals/B-factuality.md) |
| **C** | Infrastructure + Part 4 extension | `src/confqa/common/`, `src/confqa/extension/` | [docs/manuals/C-infra-extension.md](docs/manuals/C-infra-extension.md) |

- Week plan and handoff points: [docs/planning/workplan.png](docs/planning/workplan.png)
- Decisions, risks, deliverables: [PLAN.md](PLAN.md)
- Artifact formats: [docs/reference/schemas.md](docs/reference/schemas.md)

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pre-commit install
pytest
```

The core package needs only numpy and pyyaml, so tests run on a login node.
GPU dependencies live in `requirements-gpu.txt` and are needed only to
sample from a model.

## Shared tools (owner: C)

Everything that crosses a person boundary goes through these three modules, so
the numbers stay comparable and traceable.

| Tool | Use |
|---|---|
| `python -m confqa.common.splits --dataset ... --out data/splits/...` | build the committed calibration/dev/test split (run once) |
| `confqa.common.results.run_result(...)` | write a result json stamped with git commit, config hash and `reportable` |
| `confqa.common.plots.plot_coverage_vs_size` / `plot_retention_vs_factuality` | turn result jsons into the two trade-off figures |

`data/splits/factscore.json` is already built and committed (50 prompts:
25 test / 5 dev / 20 calibration pool).

## Layout

```
configs/            experiment configs; base.yaml is the single source of shared settings
data/               raw data (ignored) + fixed splits (tracked)
cache/              generated artifacts: samples, similarities, claims (ignored)
exp/results/        one json per run -- tracked, the source of every number
figures/            plots produced from exp/results
src/confqa/         common/ (shared), conu/ (A), factuality/ (B), extension/ (C)
tests/              unit tests for metrics and io
scripts/            cluster setup and slurm template
docs/manuals/       one lab manual per person
docs/planning/      work plan (Gantt + handoffs) and its generator
docs/reference/     artifact schemas, pinned upstream commits, repro checklist
third_party/        upstream repos at pinned commits (ignored)
```

## What git tracks

| Path | Tracked | Why |
|---|---|---|
| `src/`, `tests/`, `configs/`, `docs/`, `scripts/` | yes | the project itself |
| `exp/results/*.json` | yes | small, and every report number traces to one |
| `figures/*.pdf`, `figures/*.png` | yes | report assets |
| `data/splits/*.json` | yes | fixed calibration/test splits must be reproducible |
| `data/raw/`, `cache/`, `third_party/` | no | large, regenerable, or cloned |

## Working rules

- **One owner per directory.** `common/` belongs to C; do not edit another
  person's package without saying so.
- Branch per person: `feat/conu-*`, `feat/fact-*`, `feat/ext-*`.
  PR into `main`, CI green first.
- Any new artifact format goes into `docs/reference/schemas.md` **before** code.
- One json per experiment in `exp/results/`, named
  `<pipeline>__a<alpha>__calib<ratio>.json`.
- Never commit `cache/`, `data/raw/`, `third_party/`.

## Status

- [x] scaffold, CI, metrics, tests, schemas
- [x] upstream repos cloned and pinned ([docs/reference/upstream_versions.md](docs/reference/upstream_versions.md))
- [x] per-person manuals and work plan
- [ ] ConU pipeline running end to end (A)
- [x] factuality baseline from cached scores (B)
- [x] factuality H3 offline claim/judge interface (B)
- [ ] extension (C)
