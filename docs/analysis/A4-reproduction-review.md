# A4 reproduction review

A delivered two report sections and an 11 MB reproduction package on 2026-11-13.
This records what was checked before the sections were merged, and how the
package is stored.

## What arrived

| Item | Where it lives now |
|---|---|
| `A-conu-sections.md` | [A-conu-sections.md](A-conu-sections.md) |
| `A-conu-cases.md` | [A-conu-cases.md](A-conu-cases.md) |
| `a4_reproduction_handoff.zip` | `a4-evidence-20261113/`, **outside git** |

The package holds A's pipeline scripts (`a2_*.py`, `a3_run.py`,
`a4_audit.py`), the no-filter patch, seven frozen A3 inputs including the
500-question pairwise score matrix, and a bundle of the pinned upstream
checkout. All 19 files verify against its own `SHA256SUMS`.

It is **not** committed. It contains benchmark answer text and 10,000 cached
model generations, and this repository is public; A's README says the same.
`.gitignore` carries `/a4-evidence-*/` so it cannot be added by accident.

## A4 reproduces end to end

Following the package README on a third machine — Windows 11, Git Bash,
Python 3.13.0, NumPy 2.3.1, no GPU, none of A's paths present:

```bash
git clone conu-upstream.bundle third_party/ConU
git -C third_party/ConU checkout --detach c0c450e8dbef489cfed28f585f1a4ddf0e66078b
python -B a4_audit.py
```

Output:

    alpha=0.1 filtered   n_cal=243 q_hat=0.95 coverage=230/232 (99.14%) avg_set_size=18.543
    alpha=0.1 unfiltered n_cal=250 q_hat=0.95 coverage=230/250 (92.00%) avg_set_size=18.388
    alpha=0.2 (identical)

The regenerated `cache/a4_filter_audit/summary.json` hashes to
`f1be4c32…`, **byte-identical to the copy already committed at
[`exp/handoff/a5_resampling/cache/a4_filter_audit/summary.json`](../../exp/handoff/a5_resampling/cache/a4_filter_audit/summary.json)**.

## A3 recomputed from the raw scores

This is the part that did not exist before. The package carries the 20x20
pairwise similarity matrix for every one of the 500 questions, so the ConU
numbers can be rebuilt without A's code:

```python
f = (M >= 0.6).mean(axis=1)  # agreement frequency per slot
s = 1 - f / f.sum()  # upstream normalisation
ref = s[argmax(similarity_to_gold)]  # calibration reference, ties -> first
q = np.quantile(refs, ceil((n + 1) * (1 - alpha)) / n, method="higher")
keep = s <= q
```

| mode | n cal | alpha | q-hat | coverage | mean retained | distinct texts |
|---|---:|---:|---:|---:|---:|---:|
| unfiltered | 250 | 0.1 | 0.95 | 230/250 = 92.0% | 18.388 | 6.308 |
| unfiltered | 250 | 0.2 | 0.95 | 230/250 = 92.0% | 18.388 | 6.308 |
| filtered | 243 | 0.1 | 0.95 | 230/232 = 99.14% | 18.543 | 6.272 |
| filtered | 243 | 0.2 | 0.95 | 230/232 = 99.14% | 18.543 | 6.272 |

Every value matches A4's summary and Table 1 to the last digit. Short-form now
has a second, independent implementation behind it rather than a quotation.

## The five cases hold up

Each cited question was re-derived from the score matrix:

| case | claim in the section | check |
|---|---|---|
| `dpql_825` | 12 slots retained, includes Nicola Walker | kept 12/20, slots 3,5,7,10,11,12,13,14,15,17,18,20 |
| `qw_3850` | 15 slots retained, includes Cardiff, Wales | kept 15/20 |
| `odql_4634` | all 20 answers say Perth, all retained, gold is Edinburgh | kept 20/20, acceptable 0/20, **one distinct text** |
| `bt_3134` | only Mars is acceptable, nonconformity 0.997, filtered out | gold 0.750, s = 0.9970, kept 18/20, uncovered |
| `qw_4781` | slots 8 and 19 read "There seems to be a bit of confusion here", gold 0.60978 | exact, to five decimals |

Gold similarities and nonconformities in the case tables also match, e.g.
`dpql_825` slot 1: 0.54595 / 0.96711.

## Configuration claims verified

From `cache/a3_500_m20/plan.json` and `similarity/plan.json`:

- 36 max new tokens, temperature 1.0, top-p 0.9, top-k 20 — as written
- 20 samples x 500 questions; `predicted_pairs = 105000` = 500 x 210
- scorer `cross-encoder/stsb-roberta-large` at revision `2b12c2c008…` — as written
- correctness threshold 0.60; `reused_response_count = 0`

And the claim about upstream ordering is correct. At the pinned commit the
released evaluator filters first and then splits:

```python
applied_generations = [g for g in generations if max(sim[g]) >= threshold]
num_cal = int(len(applied_generations) * split_ratio)
```

A3 splits first and applies the same rule inside each partition, which is why it
can report both 99.14% on eligible questions and 92.0% on all 250.

## Not verified

- 12,720.5 s of generation, 1,666.1 s of scoring, 1.34 GiB peak allocation. The
  logs behind them (`cache/a3_500_m20/responses`,
  `similarity/sessions/1794007262216147101.json`) are not in the package; the
  checkpoints in the similarity manifest store hashes, not timestamps.
- That the A3 cache was produced by the scripts as delivered. The script hashes
  are pinned inside `plan.json` and match the copies in the package, but the run
  itself was not re-executed.

## What was changed when merging

1. **All relative links were rewritten.** A wrote them as if the files sat at
   the repository root; they now live in `docs/analysis/` and every target is
   `../../…`. All 17 relative links resolve. Links into the A3 cache and the
   pipeline scripts became plain text, because those files are deliberately not
   in this repository.
2. **The compliance paragraph was reframed** from "still needs course
   confirmation" to a stated design choice: the pinned ConU release ships only
   scripts, with no cached generations or scores, so there was nothing to
   reuse; the pool and split were frozen before generation, sampled once, and
   every later analysis runs off that one cache; the cost is 3.5 GPU-hours of
   generation (4.0 with scoring) inside the 20-hour budget. `reused_response_count
   = 0` keeps the choice visible. This is [recorded as a decision](../../PLAN.md).
3. **The case document's opening sentence** now says there are four detailed
   cases plus the similarity-proxy failure, since `qw_4781` is discussed but
   not tabulated.
