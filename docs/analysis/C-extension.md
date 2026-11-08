# Part 4: cross-response claim scoring (C)

Status: complete. Every number below comes from committed code and committed
result files; the label audit is documented in the same commit.

## What was built

1. 50 FActScore prompts x 5 responses from Qwen2.5-14B-Instruct
   (`cache/ext_responses.jsonl`, 292 s of generation).
2. H3 pipeline: 250 responses split into claims, target response judged against
   the other four (`cache/h3/`, 500 calls, 0 parse failures).
3. Extension: claims from different responses merged by cross-encoder
   similarity >= 0.6, `support = (#responses in the cluster) / 5`
   (`cache/ext/clusters.jsonl`, 550 target claims).
4. Two label sets: a memory-only LLM judge, then a retrieval-grounded relabel
   against cached Wikipedia extracts (`data/wiki_cache/`).

Both scorers use the same claims, the same labels, the same 25/25 split and the
same split-conformal rule, so the comparison is at an identical sampling budget.

## Label audit: why the first pass was thrown away

The memory-only judge labelled 550 claims. Sixteen claims were checked by hand
against Wikipedia; **6 of 17 were wrong (35%)**, in three modes:

- plausible but false (a baseball pitcher judged "football player")
- true but judged false (a Paralympic medallist judged not an athlete)
- true but off-topic (a statement about a restaurant chain counted as support
  for a claim about a musician)

The retrieval-grounded relabel fixed the source. Verdict distribution:

| verdict | count | share |
|---|---:|---:|
| not_claim | 98 | 17.8% |
| supported | 77 | 14.0% |
| contradicted | 87 | 15.8% |
| absent | 288 | 52.4% |

**17.8% of extracted "claims" are not factual assertions at all** — sentences
like "more details about X are needed". The memory-only judge marked them true,
inflating factuality; the grounded pass tags them `not_claim` and drops them.

## Does cross-response support track truth?

Among the 452 real claims:

| support | supported | contradicted | absent | supported rate |
|---|---:|---:|---:|---:|
| 0.2 | 5 | 31 | 74 | 4.5% |
| 1.0 | 66 | 50 | 188 | 21.7% |

Support carries signal — a 5x lift from 0.2 to 1.0 — but it is a weak filter:
at the strictest possible threshold, 78% of retained claims are still not
supported by the article, and **16.4% are directly contradicted**. Those are
claims all five samples agreed on and Wikipedia denies: a shared hallucination,
not random noise.

## Headline comparison (grounded labels, 25 test responses)

| method | threshold | vacuous all-correct | retention | empty rate |
|---|---:|---:|---:|---:|
| baseline (judge frequency) | 5.0 | **0.75** | 0.124 | 0.667 |
| extension (support) | 1.0 | 0.25 | **0.691** | 0.167 |

The extension keeps 5.6x more claims and is three times less reliable. Neither
reaches its nominal target (0.9 / 0.8): the baseline empties two thirds of the
responses and still misses.

For reference, the same comparison under the discarded weak labels gave 0.84 vs
0.24 — the baseline number dropped to 0.75 once labels were grounded, while the
extension barely moved. **The weak labels flattered the baseline.**

## What this means

- The extension is a **negative result**. Consistency is a real but weak signal;
  it does not separate "repeated truth" from "repeated error".
- The dominant failure mode is not the clustering threshold. Support collapses
  to 1.0 for 65% of claims because the encoder merges almost every pair at 0.6,
  so the score has almost no range to calibrate on.
- Claim decomposition itself is a source of error: one in six "claims" is
  meta-commentary.
- Under strict verification, conformal factuality filtering is hard to satisfy
  on this data at all: most generated content is simply not verifiable, so
  "remove uncertain claims" removes most of the response.

## Limitations

- "absent" is not "false": a claim can be true but absent from a 3,000-character
  extract of a short article. All absent claims are counted as unsupported,
  following the FActScore convention, which biases factuality down.
- Two entities (Joeri Adams, Carlos Alfonso) have only disambiguation pages.
- The test half holds 25 responses; every rate above has a wide interval.
- The extension's similarity threshold was fixed at 0.6 for comparability with
  the short-form line, not tuned.
