# Pilot run 2 — GPT6-Luna on 12 claims

Second adjudicator, same protocol file and the same input bytes
(`pilot_12_claims.jsonl`, sha256 `9166965979e7…`) as run 1. Neither model saw
the other's output.

## Protocol adherence

| Check | Result |
|---|---|
| records returned | 12 / 12 |
| JSON parses | 12 / 12 |
| required fields present, no extra fields | 12 / 12 |
| blind IDs match the input set and order | 12 / 12 |
| quotes found verbatim in the supplied evidence | **11 / 11** |
| quotes emitted where state is `unknown` | 2 of 5 (allowed) |

## Agreement with the FActScore human annotation

| | value |
|---|---:|
| comparable claims | 10 |
| agreement | **7 / 10** |
| Y claims supported | 6 / 9 |
| Y claims returned `unknown` | 2 / 9 |
| Y claim returned `contradicted` | 1 / 9 |
| U claim returned `unknown` | 1 / 1 |
| output distribution | supported 6, unknown 5, contradicted 1 |

## Agreement with run 1 (DeepSeek Flash)

| field | agreement |
|---|---:|
| `state` | **12 / 12** |
| `confidence` | 11 / 12 (P001: run 1 `medium`, run 2 `high`) |
| `complete_proposition` | 11 / 12 (P008: run 1 `true`, run 2 `false`) |
| `temporal_caveat` | 9 / 12 (run 2 drops the caveat on P009, adds a different one on P006) |
| quote set identical | 7 / 12 |

The three label-level disagreements with the human annotation are the *same
three* in both runs: P003 and P005 returned `unknown`, P008 returned
`contradicted`. See `runs/deepseek-flash_pilot12_2026-11-17.validation.md` for
the reading of each.

## What the two runs together show

Two adjudicators from different model families produced **identical state labels
on all 12 items**, with the same confidence on 11 of 12. That is the useful
finding: the label is driven by the protocol, not by model idiosyncrasy, so the
gap against the human annotation is a property of an evidence-only reading
rather than of one model's weakness.

It also means the ceiling is not an artefact we can dismiss by swapping models.
Evidence-only adjudication recovered 6 of the 9 human-true claims in both runs.
If that ratio holds on the 80-claim batch, an evidence-based filter has a
ceiling **below** the human-true set, and C's utility argument must be made
against that ceiling rather than against full recall.

## Caveats

- Two models, 12 claims, one run each. No third adjudicator, no repeat run, so
  there is no estimate of within-model variance.
- Decoding settings were not exposed by either harness and are unrecorded.
- The pilot claims are drawn from all 50 biographies (the test split has only 21
  score-0 claims); they are a protocol test, not a population sample.
- Per-claim labels are in `private/gpt6-luna_pilot12_comparison.json` and
  `private/pilot12_two_model_agreement.json` and must not be shown to an
  evaluator.
