# NLP-project

Conformal Prediction for Reliable Short- and Long-Form Question Answering.

Course project for **AIAA 4051 Natural Language Processing (Fall 2026)**.

Large language models answer confidently and sometimes wrongly. This project
reproduces two conformal methods — **ConU** (prediction sets that cover a
correct answer) and **conformal factuality** (claim filtering that keeps the
retained content correct) — compares what "reliable" means in each, and tests
one small extension that carries ConU's cross-sample agreement signal into
claim scoring.

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

## Layout

```
configs/        experiment configs (yaml), one file per study
data/           raw data and fixed splits (raw data is git-ignored)
cache/          generated artifacts: samples, similarities, claims (git-ignored)
exp/results/    one json per run -- tracked, this is the source of every number
figures/        plots produced from exp/results
src/confqa/     package: common/, conu/, factuality/, extension/
tests/          unit tests for metrics and io
scripts/        cluster setup and slurm submission
docs/           artifact schemas, reproduction checklist
```

## What git tracks

| Path | Tracked | Why |
|---|---|---|
| `src/`, `tests/`, `configs/`, `docs/` | yes | the project itself |
| `exp/results/*.json` | yes | small, and every report number traces to one |
| `figures/*.pdf`, `figures/*.png` | yes | report assets |
| `data/splits/*.json` | yes | fixed calibration/test splits must be reproducible |
| `data/raw/`, `cache/` | no | too large, regenerable |
| `third_party/` | no | cloned upstream repos, pinned by commit hash |

## Working together

Three people work in parallel, so keep the interfaces boring:

- Branch per person: `feat/conu-*`, `feat/fact-*`, `feat/ext-*`.
  PR into `main`, one reviewer.
- CI must be green before merge (ruff + pytest, ~30 s).
- Any new artifact format goes into `docs/schemas.md` **before** code is written.
- Every experiment writes exactly one json to `exp/results/`, named
  `<pipeline>__a<alpha>__calib<ratio>.json`; the report cites that filename.
- Do not commit anything from `cache/` or `data/raw/`.

## Compute

Target: one NVIDIA A6000-class GPU, at most 20 GPU-hours planned. School
cluster; `scripts/setup_env.sh` and `scripts/slurm/template.sbatch` carry
the TODOs to fill in for this cluster.

## Status

- [x] repository scaffold, CI, metrics, tests, schemas
- [ ] W1: both upstream repos running end to end
- [ ] W1: ConU filtering audit
- [ ] W2-W4: experiments (see `PLAN.md`)
