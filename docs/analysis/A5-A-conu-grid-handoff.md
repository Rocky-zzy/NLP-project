# A5 handoff: ConU calibration-size grid

Received 2026-11-12 from A in `a5_h5_results/`. This closes the gap flagged in
[main-tables.md](main-tables.md): the short-form side now has a second axis.

Note on numbering: A calls this handoff H5, but H5 is already B's factuality
handoff. The file name uses A5 to avoid a collision; the result files and the
config keep A's names.

## What A delivered, and where it now lives

| Item | Location in this repository |
|---|---|
| 6 result files | `exp/results/conu__a{0.1,0.2}__calib{0.4,0.6,1}.json` |
| config | `configs/conu_a5.json` |
| figure | `figures/conu_a5_coverage_vs_size.png` |
| generator | `src/confqa/conu/a5_grid.py` |
| schema note | `docs/reference/schemas.md` (section 2) |

Provenance: A's commit `9ec4c4c` ("Add reproducible ConU A5 grid", parent
`e116236`, author `Codex <codex@local.invalid>`), delivered as
`a5_h5_results/provenance/a5_source.bundle`. The bundle fetches into this
repository and the cherry-pick applied with one automatic merge and no conflict.

## The grid

Three calibration sizes from a frozen 250-question pool (nested prefixes of one
order, not independent draws), two error levels, one fixed 250-question test set.

All six cells return the same numbers:

| quantity | value |
|---|---|
| threshold | 0.95 |
| coverage, all 250 test questions | 230/250 = 0.920, 95% CI [0.884, 0.952] |
| coverage, answerable subset | 230/232 = 0.991, 95% CI [0.978, 1.000] |
| mean set size | 18.388 slots, 95% CI [17.976, 18.776] |

Quantile levels differ as they should (0.910 / 0.907 / 0.904 at alpha = 0.1;
0.810 / 0.807 / 0.804 at alpha = 0.2); only the resulting order statistic does
not move.

## Review

### Verified here

1. `configs/conu_a5.json` hashes to `2cbc0fcc…` in all six records — matches the
   file actually delivered.
2. Quantile levels are `ceil((n+1)(1-alpha))/n` for every row (n = 100, 150, 250).
3. The three calibration subsets are strict prefixes of each other and hold 250
   distinct ids with no repeats.
4. The bundle resolves to commit `9ec4c4c`, whose tree contains the script,
   config and schema note that are now on `main`.
5. Copied result files and figure are byte-identical to the handoff copies
   (sha256 checked before the staging folder was removed).
6. Every record carries `reportable: true`, `git.dirty: false`, and hash-pinned
   inputs.

### Not verified here

The numbers cannot be recomputed from this repository. A5 consumes
`cache/a3_500_m20/` (A's generation cache, gitignored) and
`cache/a4_filter_audit/summary.json`. Neither was handed over, and **A4 has still
not been delivered at all** — it is declared as an input in `input_sha256` but
never appeared. What protects the numbers is A5's own cross-check: when
n_calibration equals the full pool it asserts equality with A4's unfiltered run
and aborts otherwise, and it refuses to run on a dirty checkout.

### Problems

1. **The six cells are one experiment, not six.** Coverage and set size are
   functions of (test set, threshold) only. Once q-hat stops moving, five of the
   six files are forced to be identical. Report this as "the threshold stays on
   the same atom across calibration sizes", never as "the method is robust to
   calibration size".
2. **The confidence intervals condition on a fixed calibration set.** They
   resample test questions, so they cannot say anything about calibration
   sampling error. Identical interval widths at n = 100 and n = 250 are an
   artifact of that choice, not evidence that calibration size does not matter.
   Claiming the latter needs repeated calibration draws. This belongs in the
   limitations.
3. **`calib_frac` has two denominators in this repository.** A5 and the
   factuality files use the calibration pool (0.4 / 0.6 / 1.0); the A3 summary
   used the whole 500-question cohort (0.5). It is documented in schemas.md, but
   the field is ambiguous on its own: quote absolute counts in the report.
4. **The calibration population is not A3's.** A5 uses all 250 calibration
   questions including the 7 with no correct sample; A3 used 243 filtered ones.
   Both give 0.920 / 18.39, but the `calib1` row is not a replay of A3.
5. Minor: the figure's x-axis spans 17.53–19.23 although the maximum is 20 slots,
   which makes a 1.6-slot range look like real spread. The caption should state
   the ceiling.
6. Minor: the axis limits and the "coincident settings share one marker" note are
   good practice — the degeneracy is disclosed rather than hidden.

## Consequence for the report

Table 1 in [main-tables.md](main-tables.md) now reports both axes and gets a
flat answer. That is the honest result, and it needs to be attributed to the
upstream normalisation (ConU divides by the sum of the similarity frequencies,
which puts 196 of 243 calibration scores on exactly 0.95), not to A's
implementation.
