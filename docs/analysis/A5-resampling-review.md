# A5 resampling review

A answered the request with a 1,000-draw resampling package rather than the bare
scalars. It is the better answer: the package also carries a per-test-question
coverage cutoff, which makes the headline 230/250 reproducible **without A's
generation cache**.

Delivered 2026-11-12, stored verbatim at
[`exp/handoff/a5_resampling/`](../exp/handoff/a5_resampling/). All seven files
verify against the supplied `SHA256SUMS` (checked after copying).

## What the package contains

| File | Role |
|---|---|
| `a3_scores_export.json` | 500 questions: qid, reference nonconformity, eligibility |
| `test_coverage_cutoffs.json` | per test question, the smallest acceptable-candidate score (null = no acceptable candidate) |
| `a5_calibration_resampling.json` | the 1,000-draw results, all three sizes, both alphas |
| `a5_resample_calibration.py` | the script that produced them |
| `results/summary.json` | the A3 handoff summary (sha256 `dd3db1d8…`) |
| `cache/a4_filter_audit/summary.json` | the A4 filter audit A5 depends on (sha256 `f1be4c32…`, matches A5's `input_sha256`) |
| `README.md`, `SHA256SUMS` | A's notes and the manifest |

The A4 hash matches the value recorded inside the six A5 result files, so the
declared input and the delivered file are the same bytes.

## Independent reproduction

I re-derived the result from the two data files with my own code (uniform draws
without replacement, 1,000 per size, one shared subset across both alphas).

| calibration n | alpha | q-hat p05-p95 | max q-hat | draws with q-hat > 0.95 | coverage p05-p95 |
|---:|---:|---|---:|---:|---|
| 100 | 0.1 | 0.95-0.95 | 0.95226131 | 4 / 1,000 | 230-230 |
| 100 | 0.2 | 0.95-0.95 | 0.95000000 | 0 / 1,000 | 230-230 |
| 150 | 0.1 | 0.95-0.95 | 0.95000000 | 0 / 1,000 | 230-230 |
| 150 | 0.2 | 0.95-0.95 | 0.95000000 | 0 / 1,000 | 230-230 |
| 250 | 0.1 | one subset | 0.95000000 | 0 / 1 | 230-230 |
| 250 | 0.2 | one subset | 0.95000000 | 0 / 1 | 230-230 |

Agreement: the percentiles, the maximum (0.95226131 to eight decimals) and the
coverage count are identical. The one number that does not reproduce exactly is
A's "7 of 1,000 draws above 0.95" at n = 100, alpha = 0.1; I get 4. That is an
RNG-stream difference, not a disagreement. **Do not quote the exact count in the
report** — quote the rate (about 0.5%) and the ceiling.

## Why it is flat, in arithmetic

- Of the 250 calibration scores, **199 are exactly 0.95**, 12 are above and 39
  below.
- q-hat at n = 100, alpha = 0.1 is the 91st smallest of 100 draws. It stays at
  0.95 unless at least 10 of the 100 land above 0.95, which happens about 0.5%
  of the time.
- When it does move, the maximum is 0.95226131, and the smallest test coverage
  cutoff above 0.95 is **0.98**. No observed threshold gets near it.

So the flat table is forced by the score distribution, not luck of the draw.

## What this licenses, and what it does not

**Licensed.** "With 1,000 random calibration subsets at each size, q-hat left
0.95 in at most 0.7% of draws and never crossed a coverage breakpoint; coverage
was 230/250 in all 3,000 draws." That is a real sensitivity check on the fixed
split and it replaces the weaker prefix-only statement.

**Not licensed.** "ConU is insensitive to calibration size" as a
distribution-free claim. This is an empirical statement about one fixed 250/250
split with one cached score matrix. A is also right to push back on my framing:
`1/(n+1)` is the marginal-coverage correction for split conformal under no
ties, a bound on expected coverage, not a measure of how much q-hat varies
across calibration draws. I conflated the two in the request.

## Two corrections to A's README

**1. "218/250" mixes two denominators.** The README says using the reference
score would give 218/250 where the candidate minimum gives 230/250. Measured:

| rule | over the fixed 250 | over the 232 answerable |
|---|---:|---:|
| candidate minimum at or below 0.95 (correct) | 230 | 230 |
| reference score at or below 0.95 (shortcut) | **231** | **218** |

The 218 is the 232-subset count printed against the 250-question total. The
shortcut is not "12 questions worse": it is 1 question better in aggregate,
because it miscounts 13 unanswerable questions as covered and misses 12
answerable ones — 25 disagreements that almost cancel. That cancellation is the
interesting part and is worth one sentence in the report.

**2. The rank is one order statistic higher than the textbook formula.** A5
computes `np.quantile(scores, k/n, method="higher")` with
`k = ceil((n+1)(1-alpha))`. For k < n that returns the (k+1)-th smallest, not
the k-th: with n = 100, k = 91 it returns s[91] instead of s[90]. The rest of
this repository (`factuality/conformal.py`, `extension/evaluate.py`) uses the
k-th. On this data both ranks hold the same value in 1,000 of 1,000 draws,
because both land inside the 0.95 atom, so **no reported number changes** — but
the threshold is slightly conservative and the report should not state the
textbook formula while the code computes one rank above it.

## Still missing

- A4's patch (`patches/conu-no-filter.patch`, hash `017e8f6a…`) is referenced by
  the A4 summary and was not delivered, so A4 cannot be re-run from this package.
- A3's generation cache is still not in the repository. It no longer blocks
  anything: the scalar export plus the cutoffs reproduce the coverage number.

## Effect on the report

Table 1 in [main-tables.md](main-tables.md) keeps the six committed A5 cells and
now adds the resampling sentence. The Part 3 short-form paragraph can say the
sensitivity was actually measured, and the limitations can still say the claim
is dataset-conditional.
