# H5 Handoff: B Factuality Results

## Status

- Owner: B
- Consumer: C
- Result generation and interpretation are complete.
- C should consume these files for the combined report and extension
  comparison.

## Result files

| Target | Calibration n | Result file |
|---:|---:|---|
| 0.9 | 10 | `exp/results/fact__a0.1__calib0.5.json` |
| 0.9 | 15 | `exp/results/fact__a0.1__calib0.75.json` |
| 0.9 | 20 | `exp/results/fact__a0.1__calib1.json` |
| 0.8 | 10 | `exp/results/fact__a0.2__calib0.5.json` |
| 0.8 | 15 | `exp/results/fact__a0.2__calib0.75.json` |
| 0.8 | 20 | `exp/results/fact__a0.2__calib1.json` |

All six files:

- have `pipeline="fact"`;
- have `reportable=true`;
- contain the same `test_ids_sha256`;
- contain the same split and scored-input hashes;
- record their calibration IDs explicitly.

## Headline numbers

| Target | Calib n | Threshold | All-correct | Retention | Empty |
|---:|---:|---:|---:|---:|---:|
| 0.9 | 10 | 5.00007 | 0.60 | 0.1619 | 0.36 |
| 0.9 | 15 | 5.00007 | 0.60 | 0.1619 | 0.36 |
| 0.9 | 20 | 4.99964 | 0.68 | 0.2143 | 0.28 |
| 0.8 | 10 | 4.99876 | 0.80 | 0.2952 | 0.12 |
| 0.8 | 15 | 4.99876 | 0.80 | 0.2952 | 0.12 |
| 0.8 | 20 | 3.99988 | 0.76 | 0.3619 | 0.12 |

Every point includes response-level bootstrap 95% intervals for all three
metrics. Detailed intervals and interpretation are in
`docs/analysis/B-grid.md`.

## Related assets

- Main figure: `figures/retention_vs_factuality.png`
- PDF figure: `figures/retention_vs_factuality.pdf`
- Case analysis: `docs/analysis/B-factuality-cases.md`
- Report draft: `reports/B-factuality-sections.md`

## Regeneration commands

Rebuild all six results from a clean checkout:

```bash
PYTHONPATH=src .venv/bin/python -m confqa.factuality.cli grid \
    --config configs/factuality.yaml
```

Rebuild the figure:

```bash
PYTHONPATH=src .venv/bin/python -m confqa.factuality.cli report
```

Validate reportability:

```bash
jq -e '.reportable == true' exp/results/fact__*.json
```

## C acceptance checks

- Confirm all six result files exist.
- Confirm the combinations are exactly two alpha values × three calibration
  values.
- Confirm `n_calibration` is 10/15/20 according to `calib_frac`.
- Confirm all test ID hashes are identical.
- Use `reports/B-factuality-sections.md` rather than copying values manually.

## Not included

- Qwen generation.
- H3 real-model execution.
- Extension baseline and semantic-clustering results.
- C's independent reproduction.

