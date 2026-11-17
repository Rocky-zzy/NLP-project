# Pilot run 1 — DeepSeek Flash on 12 claims

## Protocol adherence

| Check | Result |
|---|---|
| records returned | 12 / 12 |
| JSON parses | 12 / 12 |
| required fields present | 12 / 12 |
| quotes found verbatim in the supplied evidence | **12 / 12** |
| quotes emitted where state is `unknown` | 1 of 5 (allowed) |

The quote check is the cheapest evidence that the passage was actually read: a
model inventing quotes cannot pass it.

## Agreement with the FActScore human annotation

Compared on the subset where evidence can in principle decide the claim
(`Y`→supported, `N`→contradicted, `U`→unknown). The two `S` (subjective)
claims are excluded from the primary rate; both were returned as `unknown`,
which is the expected behaviour rather than an error.

| | value |
|---|---:|
| comparable claims | 10 |
| agreement | **7 / 10** |
| Y claims supported | 6 / 9 |
| Y claims returned `unknown` | 2 / 9 |
| Y claim returned `contradicted` | 1 / 9 |
| U claim returned `unknown` | 1 / 1 |
| output distribution | supported 6, unknown 5, contradicted 1 |

## The three disagreements, and why they matter

1. **P003** (`Y` → `unknown`). The claim is that Flaherty was born in
   Pontotoc, Mississippi. The passage says he graduated from Pontotoc High
   School; it never states a birthplace. Under an evidence-only protocol
   `unknown` is the correct output. The human label is probably true, but it is
   not supported by *this passage*.
2. **P005** (`Y` → `unknown`). A claim about a friendship with Hadrian; the
   passage never mentions Hadrian.
3. **P008** (`Y` → `contradicted`). The claim calls the subject a professional
   athlete; the passage describes him as a **retired** footballer. This is a
   temporal disagreement, and the model flagged the retrieval date. The human
   annotation was made in 2023, the passage was read in 2026.

None of these is a reasoning failure. They are the measurement we wanted:
evidence-only adjudication and a human annotator answer **different questions**,
and the gap is largest for facts that the article does not state.

## What this implies for the evidence audit

For this pilot, external evidence directly established 6 of the 9 claims that a
human marked true. The remaining 3 were silent or temporally shifted. If that
ratio holds on the 80-claim batch, an evidence-based filter has a **ceiling
below the human-true set**, and C's utility gain must be argued against that
ceiling rather than against full recall.

## Caveats

- One model, 12 claims, one run. No second adjudicator has seen these items yet.
- Decoding settings were not exposed by the harness and are therefore unrecorded.
- The pilot claims are drawn from all 50 biographies (the test split has only 21
  score-0 claims); they are a protocol test, not a population sample.
- Per-claim labels are in `private/deepseek-flash_pilot12_comparison.json` and
  must not be shown to the second model.
