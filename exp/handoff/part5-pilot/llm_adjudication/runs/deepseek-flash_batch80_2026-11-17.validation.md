# Run 4 — DeepSeek Flash on the full 80-claim batch

Primary sample: all 80 blind claims, dispatched as four conversations of 20.
Scored with the corrected label mapping (see run 3).

## Protocol adherence

| Check | Result |
|---|---|
| records returned | 80 / 80 |
| blind IDs complete and in order | 80 / 80 (F001–F080) |
| quotes found verbatim in the supplied evidence | **89 / 89** |
| JSON parses without repair | 78 / 80 |
| confidence: high / medium / low | 70 / 10 / 0 |

The two parse failures are the same defect: **F002** and **F009** put unescaped
double quotes inside `temporal_caveat` (`uses "former,"`). The raw file keeps
them exactly as received; `parsed.jsonl` applies one documented repair —
escaping those quotes — and `repairs.json` records the change. Nothing else was
altered.

## Output distribution

supported 23, unknown 49, contradicted 8.

## Agreement with the FActScore annotation

FActScore's `N` means "the article does not support the claim", which covers
both contradiction and silence, so it is scored as agreement for either
`contradicted` or `unknown`.

| annotation | n | supported | contradicted | unknown |
|---|---:|---:|---:|---:|
| `Y` | 38 | 22 | 1 | 15 |
| `N` | 21 | 0 | 6 | 15 |
| `U` | 13 | 0 | 1 | 12 |
| `S` (excluded) | 8 | 1 | 0 | 7 |

| | value |
|---|---:|
| comparable | 72 |
| agreement, `N` as not-supported | **55 / 72 = 76.4%** |
| agreement, strict `N`→contradicted | 40 / 72 = 55.6% |

## The two numbers that matter

| | value |
|---|---:|
| **precision of a `supported` verdict** | **22 / 23 = 95.7%** |
| **recall on human-true claims** | **22 / 38 = 57.9%** |

The only `supported` output that is not a human-`Y` claim is F017, a subjective
claim about being "known for exceptional skill"; GPT6-Luna returned the same
verdict on it. So the evidence channel is **precise but incomplete**: when it
certifies a claim it is right about 96% of the time, and it certifies 58% of what
a human annotator calls true.

## The two `contradicted` outputs that were not `N`

Both were inspected and both are defensible:

- **F014** (annotated `Y`). "Rennie Fritchie is a crossbench member of the House of
  Lords." The passage says she sat as a crossbencher, retired on 1 July 2024 and
  died on 12 March 2026. At the 2026-11-08 retrieval date the present-tense claim
  is false. This is the same temporal pattern as pilot P008: the annotation is
  older than the evidence.
- **F046** (annotated `U`). "Lees Knowles was made a baronet in 1917." The passage
  says the 1903 Birthday Honours. The model is straightforwardly right; FActScore
  marked the claim uncertain.

Neither is a hallucination. Both are cases where the human label and the passage
answer different questions.

## Cross-model agreement

20 claims were adjudicated by both models:

| | value |
|---|---:|
| identical state | **18 / 20** |
| differences | F005 (unknown vs supported), F021 (supported vs unknown) |

- **F005** is a disambiguation page (`Carlos Alfonso may refer to:`) and the
  extracted "claim" is a meta-statement that the name is ambiguous. GPT6-Luna
  counted the page as supporting it; DeepSeek Flash did not. Both readings are
  reasonable, and neither is a factual error.
- **F021** asks whether Foppert became a coach *after* retiring. The passage states
  both facts but not their order. DeepSeek Flash inferred the order;
  GPT6-Luna refused to. GPT6-Luna's reading is the stricter one and matches the
  protocol's rule 3.

## What this means for Part 4

The evidence channel has a **hard coverage ceiling**. It can certify 58% of the
human-true claims; the other 42% are invisible to it, not misjudged by it. That
bounds what any better filter can buy: precision can rise toward 96%, but recall
cannot rise without a different evidence source (full articles, revision IDs,
multiple sources), which is out of scope here.

This is the same precision/coverage frontier the conformal analysis trades
against, and it is the honest limit on the utility claim in Part 4.

## Caveats

- One model on the full 80; the second model saw only 20 of them.
- Evidence was capped at 12,000 characters and retrieved on 2026-11-08; 25 of the
  80 extracts are under 2,000 characters, and for those `unknown` is expected.
- The `Y` recovery rate is stable across three samples — 6/9 (67%) in the pilot,
  4/7 (57%) in the 20-claim subset, 22/38 (58%) here — so it is likely a real
  property of the evidence, not sampling noise.
- Annotations were made in 2023; several claims are present-tense and the
  evidence is from 2026.
- Per-claim annotations are in `private/deepseek-flash_batch80_comparison.json`
  and must never be shown to an evaluator.
