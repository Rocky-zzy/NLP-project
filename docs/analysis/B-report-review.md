# B report review

B delivered the long-form report sections on a branch
(`feat/fact-final-report`, merged as `b59816f`). This records what was checked.

## What arrived

| Item | Note |
|---|---|
| [reports/B-factuality-sections.md](../reports/B-factuality-sections.md) | 396 lines: Parts 1b, 2b, 3b, limitations, references |
| `src/confqa/factuality/report.py` | new 255-line figure builder |
| `src/confqa/factuality/cli.py` | gains a `report` subcommand |
| `tests/test_factuality_report.py` | 28 new lines |
| `figures/factuality_claim_diagnostics.{png,pdf}` | new Figure 1 |
| `figures/retention_vs_factuality.{png,pdf}` | regenerated Figure 2 |

Merged cleanly despite a 21-commit divergence; the touched files do not overlap
main's recent work. `ruff` and `pytest` pass on the merged tree (55 tests).

## Recomputed from the upstream cache

Everything below was recomputed from
`third_party/conformal-factual-lm/out/factscore_subclaims_with_scores.jsonl`
with an independent implementation (rank score, `ceil((n+1)(1-alpha))`
quantile, retain when `frequency + noise >= tau`), not by calling B's code.

| Claim | Reported | Recomputed |
|---|---|---|
| prompts / claims | 50 / 408 | 50 / 408 |
| split | 25 test, 5 dev, 20 pool | identical |
| threshold (20 calib, 0.9) | 4.999642 | 4.999642 |
| vacuous / nonempty / retention / empty | 0.96 / 0.68 / 0.2143 / 0.28 | 24/25, 17/25, 45/210, 7/25 |
| response outcomes | 17 correct, 7 empty, 1 with N | identical |
| test claims by annotation | Y111 S24 N52 U23 | identical |
| retained by annotation | 40 / 4 / 1 / 0 | identical |
| precision / recall | 97.8% / 32.6% | 44/45, 44/135 |
| N/U removed | 74 of 75 | identical |
| correct-claim score table | 66/44/22, 12/0/12, 45/0/45, 2/0/2, 10/0/10 | identical |
| merged file: rows with no accepted claim | four, all `Abstain.` | 4 of 50 |

The 95% intervals in B's tables also match the committed `exp/results/fact__*.json`
files exactly, including the [0.104, 0.223] retention interval at 10 calibration
responses. The six-cell grid reproduces as: 0.9 → thresholds 5.00007 (n=10,15)
and 4.999642 (n=20); 0.8 → 4.99876 (n=10,15) and 3.999881 (n=20).

## Two wording fixes worth making before submission

1. **Percentages over "retained/dropped" mix denominators.** The sentence
   "Subjective `S` claims are 9.1% of retained claims but 22.0% of dropped
   claims" only works if "retained" means the 44 retained *correct* claims and
   "dropped" the 91 dropped *correct* claims. Against all 45 retained and 165
   dropped claims the shares are 8.9% and 12.1%. The same applies to the
   compound-claim (11.4% / 17.6%) and pronoun (6.8% / 18.7%) sentences. One
   phrase — "among correct claims" — fixes all three.
2. **Figure regeneration is not byte-stable.** The PDFs embed a `CreationDate`,
   so rerunning `python -m confqa.factuality.cli report` always dirties the
   working tree. The PNGs are deterministic within one machine but differ
   across machines: B's Figure 1 is 2442x981, the same figure here is 2440x977,
   because `bbox_inches="tight"` depends on font metrics. The content is
   identical. Not worth changing before freeze, but do not treat a dirty
   `figures/` after regeneration as a real diff.

## Scope

B marks the branch as `upstream-cached:gpt-4` and states plainly that it
reproduces calibration and filtering from the released cache without deploying
a generator. That is consistent with the course brief's requirement to use
existing cached outputs for the main experiment, and it is the contrast worth
drawing against the short-form branch, which had no released cache to reuse.
