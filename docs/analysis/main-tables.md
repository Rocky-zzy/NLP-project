# Main tables (Parts 1-3)

Numbers below are copied from committed result files, not retyped. Regenerate
with the commands at the end.

---

## Table 1 — Short-form (ConU, 500 TriviaQA questions x 20 samples)

Source: `exp/results/conu__a<alpha>__calib<frac>.json` (A5). One fixed
250-question test set; the three calibration sizes are nested prefixes of a
single frozen order, so they are not independent draws. See
[A5-A-conu-grid-handoff.md](A5-A-conu-grid-handoff.md) for the review.

| alpha | n calibration | q-hat | quantile level | coverage, all 250 [95% CI] | coverage, eligible 232 | set size, slots [95% CI] |
|---:|---:|---:|---:|---:|---:|---:|
| 0.1 | 100 | 0.95 | 0.910 | 0.920 [0.884, 0.952] | 0.991 | 18.388 [17.976, 18.776] |
| 0.1 | 150 | 0.95 | 0.907 | 0.920 [0.884, 0.952] | 0.991 | 18.388 [17.976, 18.776] |
| 0.1 | 250 | 0.95 | 0.904 | 0.920 [0.884, 0.952] | 0.991 | 18.388 [17.976, 18.776] |
| 0.2 | 100 | 0.95 | 0.810 | 0.920 [0.884, 0.952] | 0.991 | 18.388 [17.976, 18.776] |
| 0.2 | 150 | 0.95 | 0.807 | 0.920 [0.884, 0.952] | 0.991 | 18.388 [17.976, 18.776] |
| 0.2 | 250 | 0.95 | 0.804 | 0.920 [0.884, 0.952] | 0.991 | 18.388 [17.976, 18.776] |

Context that must accompany this table:

- **25 of 500 questions (5.0%) were excluded** because no sample was correct;
  18 of them sit in the test set, which is why the eligible column has n = 232.
- The oracle ceiling on all 250 test questions is **0.928** (232/250 have at
  least one correct sample), so 0.920 is within one question of the maximum
  attainable. 0.92 versus a 0.90 target is not evidence of a well-behaved
  method; it is a method that already returns almost everything.
- **All six rows are identical.** q-hat sits on an atom of the nonconformity
  distribution (196 of 243 calibration values are exactly 0.95 in the A3 run),
  so neither the error level nor the calibration size can move the threshold.
  The correct sentence is "the threshold stays on the same atom", not "ConU is
  robust". Once the threshold is fixed, every downstream number is forced.
- The A3 run, with a filtered 243-question calibration set and a different
  filtering convention, reproduces 0.920 / 18.39 exactly. It also reports a
  distinct-text set size of **6.31**: 18.39 of 20 returned slots cover only
  about six different answers. Report both, or the set looks useless when it is
  merely repetitive.

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

- **Both Part 3 axes are flat on the short-form side.** The grid in Table 1 moves
  neither the threshold nor any reported number. Write this up as a property of
  the upstream score normalisation, with the saturation evidence, rather than
  hiding it behind a "robustness check" heading.
- **The confidence intervals condition on a fixed calibration set**, so they
  resample test questions only. They cannot support "calibration size does not
  matter": with 100 calibration questions the quantile is far less stable, and
  nothing in these six files measures that. Needs repeated calibration draws and
  belongs in the limitations. This is the one gap a reviewer is most likely to
  find, so state it before they do.
- A3's `results/summary.json` still lives only in A's handoff and not in this
  repository. Commit it, or at least pin its sha256, before the report is final.
- A4's filter audit (`cache/a4_filter_audit/summary.json`) is a declared input of
  A5 and has never been delivered. The 25-question exclusion count cannot be
  re-derived from anything in this repository.

## How to regenerate

```bash
# short-form: needs A's cache, which is not in this repository
python -m confqa.conu.a5_grid --input-root <root> --output-dir exp/results \
    --figure figures/conu_a5_coverage_vs_size.png

ls exp/results/fact__*.json    # long-form sources
ls exp/results/conu__*.json    # short-form sources
```

The table numbers were transcribed from the committed jsons, not retyped from a
console. Re-derive any of them by reading the json directly.
