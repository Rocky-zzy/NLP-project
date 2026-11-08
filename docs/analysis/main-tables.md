# Main tables (Parts 1-3)

Numbers below are copied from committed result files, not retyped. Regenerate
with the commands at the end.

---

## Table 1 — Short-form (ConU, 500 TriviaQA questions x 20 samples)

Source: A3 handoff, `results/summary.json` (schema `confqa.conu.a3_result.v1`).

| alpha | 1-alpha | q-hat | n calibration | coverage, all 250 | coverage, eligible 232 | set size (slots) | set size (unique) |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.1 | 0.9 | 0.95 | 243 | 0.920 | 0.991 | 18.39 | 6.31 |
| 0.2 | 0.8 | 0.95 | 243 | 0.920 | 0.991 | 18.39 | 6.31 |

Context that must accompany this table:

- **25 of 500 questions (5.0%) were excluded** because no sample was correct.
- The oracle ceiling on all 250 test questions is **0.928** (232/250 have at
  least one correct sample), so 0.920 is within one question of the maximum
  attainable.
- The two alpha rows are **identical**: q-hat sits on an atom of the
  nonconformity distribution (196 of 243 calibration values are exactly 0.95),
  so the error level cannot move the threshold.

## Table 2 — Long-form (conformal factuality, 50 FActScore biographies)

Source: `exp/results/fact__a<alpha>__calib<frac>.json`.

| alpha | 1-alpha | calibration fraction | threshold | all correct (vacuous) | all correct (non-empty) | retention | empty rate |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.1 | 0.9 | 0.50 | 5.0001 | 0.960 | 0.600 | 0.162 | 0.360 |
| 0.1 | 0.9 | 0.75 | 5.0001 | 0.960 | 0.600 | 0.162 | 0.360 |
| 0.1 | 0.9 | 1.00 | 4.9996 | 0.960 | 0.680 | 0.214 | 0.280 |
| 0.2 | 0.8 | 0.50 | 4.9988 | 0.920 | 0.800 | 0.295 | 0.120 |
| 0.2 | 0.8 | 0.75 | 4.9988 | 0.920 | 0.800 | 0.295 | 0.120 |
| 0.2 | 0.8 | 1.00 | 3.9999 | 0.880 | 0.760 | 0.362 | 0.120 |

Reading rules:

- **"vacuous" is the quantity the guarantee bounds** (an emptied response counts
  as correct). Both alpha levels meet their target: 0.96 >= 0.90 and 0.92 >= 0.80.
- **"non-empty" is the usefulness-side headline.** Reporting it alone makes the
  guarantee look violated at alpha = 0.1 (0.60), which is the wrong reading.
- The cost is visible in the empty rate: at alpha = 0.1, **36% of responses are
  emptied**.
- Calibration fraction 0.5 and 0.75 give identical results because the conformal
  quantile falls on the same atom of the score distribution.

## Table 3 — What the two objectives actually measure

| | short-form (ConU) | long-form (factuality) |
|---|---|---|
| output | a set of sampled answers | a filtered response |
| guarantee | at least one correct answer in the set | every retained claim is correct |
| headline metric | coverage, set size | all-correct rate, retention, empty rate |
| cost of being conservative | larger set (here: 18.4 of 20 slots) | more emptied responses (here: 36%) |
| observed failure at the limit | set saturates near the full sample | response is emptied |

The two numbers are **not interchangeable**: 0.92 coverage is achieved by
returning almost every sample, while 0.96 factuality is achieved by deleting
36% of responses entirely.

---

## Gaps

- **Short-form has no calibration-size grid.** A3 ran only a single 250/250
  split, so the second Part 3 axis exists only on the long-form side. Treat any
  "calibration size affects short-form" statement as unsupported until A4 lands.
- A3's summary lives in the handoff bundle, not in this repository. Commit it
  (or its hash) before the report is finalised.

## How to regenerate

```bash
python ../.review-a3/tables.py          # prints every number above
ls exp/results/fact__*.json             # long-form sources
```
