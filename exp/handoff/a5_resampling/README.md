# ConU A5 calibration-subset sensitivity

Each of the three calibration sizes uses 1,000 seeded random draws from the same 250-question A3 calibration pool. Sampling is uniform without replacement within each draw. Both alpha settings share the same subset for each draw, and all draws use the same 250 held-out test questions. Calibration and evaluation follow the A5 unfiltered setting.

| Calibration n | Alpha | q̂ p05–p95 | Fixed-test coverage p05–p95 |
|---:|---:|---:|---:|
| 100 | 0.1 | 0.95–0.95 | 92.0%–92.0% |
| 100 | 0.2 | 0.95–0.95 | 92.0%–92.0% |
| 150 | 0.1 | 0.95–0.95 | 92.0%–92.0% |
| 150 | 0.2 | 0.95–0.95 | 92.0%–92.0% |
| 250 | 0.1 | 0.95–0.95 | 92.0%–92.0% |
| 250 | 0.2 | 0.95–0.95 | 92.0%–92.0% |

At n=100 and alpha=0.1, q̂ exceeds 0.95 in 7 of 1,000 draws, with a maximum of 0.95226131. The next fixed-test coverage breakpoint is 0.980000, so all observed cutoffs cover the same 230 questions. The full unfiltered calibration pool has 199 of 250 scores at 0.95. The A3 filtered pool has 196 of 243 at that value.

These percentile ranges measure sensitivity to the calibration subset on the fixed pools and cached scores. The full pool has one distinct 250-question subset. The original A5 intervals instead resample test questions with calibration fixed.

## Reproduce

Run the command from this folder with Python 3.10 or later.

    python a5_resample_calibration.py --seed 0 --draws 1000 --out a5_resampling_recomputed.json

The score export contains exactly one qid, reference score and eligibility flag per question. For coverage, test_coverage_cutoffs.json gives the minimum nonconformity among the acceptable candidates for each test question. Null denotes zero acceptable candidates. A question is covered exactly when its non-null minimum is at or below q̂. At 0.95, using the reference score instead would give 218/250, while the candidate minimum gives 230/250.

## Source summaries

- results/summary.json is the exact A3 handoff summary. SHA256 dd3db1d8d3616bec4bb871cbda6676ffdc7fe0d8eabd240c065e8fd6101e0f74
- cache/a4_filter_audit/summary.json is the exact input referenced by the A5 JSONs. It records 25/500 exclusions (5.0%). SHA256 f1be4c3201a1169217e0340a6767b30fb3914e38802795ba6fe03a10b0d36311
- a5_calibration_resampling.json includes p05, p95, observed minima and maxima, and counts for each observed threshold and coverage pair.
