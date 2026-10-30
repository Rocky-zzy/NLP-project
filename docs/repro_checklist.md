# Reproduction checklist

Tick these in order. Nothing here needs a model until step 3.

## 0. Environment

- [ ] `python -m venv .venv && source .venv/bin/activate`
- [ ] `pip install -e ".[dev]"`
- [ ] `pytest` passes (metrics + io only, no GPU)
- [ ] `pre-commit install`

## 1. Upstream repositories

- [x] `git clone https://github.com/Zhiyuan-GG/Conformal-Uncertainty-Criterion third_party/ConU`
- [x] `git clone https://github.com/tatsu-lab/conformal-factual-lm third_party/conformal-factual-lm`
- [x] Record both commit hashes: see `docs/upstream_versions.md`
- [ ] Confirm the ConU model paths can be overridden by CLI flags instead of source edits

## 2. Data

- [ ] Download TriviaQA `rc.nocontext` into `data/raw/triviaqa/`
- [x] Confirmed: `data/factscore_annotations.jsonl` ships **50** annotated prompts,
      and `out/factscore_subclaims_with_scores.jsonl` ships precomputed scores, so
      no annotation pass is needed (see `docs/upstream_versions.md`)
- [ ] Build `data/splits/`: fixed calibration / dev / test ids, commit, record sha256

## 3. ConU end to end (50 questions)

- [ ] Sample with `num_samples=20`; write `cache/conu_generations.jsonl`
- [ ] Compute similarities; write `cache/conu_scores.jsonl`
- [ ] Run the conformal step at `alpha=0.1`; write one json to `exp/results/`
- [ ] **Locate the filter** that drops questions with no correct sample; note the
      line number and whether it runs before or after the split

## 4. ConU filtering audit

- [ ] Rerun with the filter disabled (`drop_unanswerable: false`)
- [ ] Report `n_dropped_unanswerable / n_total`
- [ ] Compare filtered vs unfiltered coverage in the same table

## 5. Factuality end to end (10 biographies)

- [ ] Split responses into claims
- [ ] Score claims (judge or repo method)
- [ ] Calibrate a threshold; write one json to `exp/results/`
- [ ] Spot-check 20 claims by hand; record agreement

## 6. Extension (only after 3-5 are green)

- [ ] 50 prompts x 5 responses, generated once, cached
- [ ] Cluster equivalent claims across responses; compute support
- [ ] Filter with support scores; recalibrate at the same alpha
- [ ] Compare against the baseline at the **same sampling budget**
