# H7 Handoff: B Factuality Draft to C

## Status

- Prepared locally by B on 2026-11-05.
- Intended H7 milestone: 2026-11-23.
- Not yet sent or independently reproduced by C.

## Handoff content

| Item | Path | Status |
|---|---|---|
| Report sections 1b/2b/3b | `reports/B-factuality-sections.md` | Ready for review |
| Six result JSON files | `exp/results/fact__a[alpha]__calib[frac].json` | Reportable |
| Main figure | `figures/retention_vs_factuality.png` | Ready |
| Report PDF figure | `figures/retention_vs_factuality.pdf` | Ready |
| Detailed case analysis | `docs/analysis/B-factuality-cases.md` | Ready for review |
| Grid analysis | `docs/analysis/B-grid.md` | Ready |
| Baseline interpretation | `docs/analysis/B-baseline.md` | Ready |

## Required C acceptance checks

- Open `reports/B-factuality-sections.md` and verify that 1b, 2b, and 3b can
  be integrated without rewriting the argument.
- Confirm that every reported number names an `exp/results/*.json` source.
- Confirm that all six result files have `reportable=true`.
- Regenerate the figure with:

```bash
PYTHONPATH=src .venv/bin/python -m confqa.factuality.cli report
```

- Run the case analysis with:

```bash
PYTHONPATH=src .venv/bin/python -m confqa.factuality.cli cases \
    --config configs/factuality.yaml
```

- Check that the output reports threshold `4.999642...`, 10 calibration
  responses are a subset of 15, and 15 are a subset of 20.

## Claims C must preserve

- This branch reproduces calibration, filtering, and evaluation from cached
  GPT-4 claims and scores. It does not reproduce new generation end to end.
- `Y/S` are accepted; `N/U` are not accepted.
- `U` means unverifiable, not false.
- The primary case analysis uses \(1-\alpha=0.9\) and all 20 calibration
  responses.
- Empty responses are reported separately and are not treated as useful
  all-correct answers.
- Frequency score measures cross-sample support rather than external truth.
- The 25-response test set supports descriptive conclusions only.

## Not included in H7

- H3 real-model integration and C's independent run. The offline H3 interface
  is now documented separately in `docs/analysis/H3-B-to-C-handoff.md`.
- New Qwen generation or end-to-end model deployment.
- Independent execution by C.

H7 does not certify H3's real response-generation path.
