# Run 5 — Package B, the paired truncation probe

DeepSeek Flash adjudicated `part4_40_blind.jsonl`: 40 Part 4 claims under two
evidence conditions, `first_3000` (the extract cut where `relabel.py` cut it) and
`full` (the whole cached extract). The two copies of a claim were never dispatched
in the same chunk, so the paired comparison is not contaminated by the adjudicator
seeing its own earlier answer.

## Protocol adherence

| Check | Result |
|---|---|
| records returned | 80 / 80 |
| blind IDs match the dispatched chunks | 80 / 80 |
| quotes found verbatim in the supplied evidence | **44 / 44** |
| JSON parses without repair | 80 / 80 |
| output distribution | unknown 72, supported 4, contradicted 4 |

## 1. The adjudicator is not deterministic

Sixteen of the 40 claims have an extract under 3,000 characters, so both
conditions are **byte-identical**. They act as a free test-retest check, and it
fails two of sixteen (**14/16 = 87.5%**):

| claim | truncated copy | full copy | why they differ |
|---|---|---|---|
| Tusa, "is an Italian archaeologist" | X075 `supported` | X004 `contradicted` | one read the past tense plus the dates as temporally contradicting a present-tense claim; the other treated the claim as a historical occupation |
| Fernando, "is a defensive midfielder" | X020 `contradicted` | X045 `unknown` | one treated "goalkeeper" as incompatible; the other refused to contradict a claim the passage never mentions |

This is the single most important number in the run, and it is not in the paper
we are reproducing. **The measurement floor is 12%.** Any difference smaller than
that — including the 16.4% contradiction rate we set out to explain — is inside
the adjudicator's own noise on this sample size.

## 2. Truncation is not what drives the label

Twenty-four claims have genuinely different evidence between conditions. Only
**one of the 24 flipped**:

- X013 (`full`, 4,805 chars) returned `supported` on "Valpy produced public
  affairs documentaries"; X077 (`first_3000`, 3,000 chars) returned `unknown`.

The direction matters. The full text earned the *stronger* verdict, so removing
the last 1,800 characters made the adjudicator more cautious. That is exactly the
direction predicted by the semantics of the protocol: a `contradicted` or
`supported` verdict needs positive evidence inside the visible window, so hiding
text can only turn those into `unknown`, never the reverse.

The empirical answer to the A4 confound is therefore: **the 3,000-character cap
makes the reported rates conservative, not inflated.** 23 of 24 pairs did not
change at all.

## 3. The two protocols disagree about absence

The package deliberately oversamples claims the grounded labels call
`contradicted` (20 of 40). Here is what the adjudicator made of them:

| grounded verdict | condition | supported | contradicted | unknown |
|---|---|---:|---:|---:|
| `contradicted` (21) | `first_3000` | 0 | 2 | 19 |
| `contradicted` (21) | `full` | 0 | 1 | 20 |
| `absent` (12) | `first_3000` | 0 | 0 | 12 |
| `absent` (12) | `full` | 1 | 0 | 11 |
| `supported` (3) | `first_3000` | 2 | 0 | 1 |
| `supported` (3) | `full` | 1 | 1 | 1 |
| `not_claim` (4) | both | 0 | 0 | 4 |

The adjudicator recovers **3 of the 21 contradictions** the grounded judge
recorded, and calls the other 18 `unknown`.

That is not a failure of either system; it is a disagreement about what
"contradicted" means for a hallucinated biography. The Part 4 claims are
fabrications about a real person — "Foppert was an NFL kicker", "Arbore was a
renowned musician". The article about Foppert says he is a baseball pitcher and
never mentions football. The grounded judge read that as *contradicted*; the
adjudication protocol reads it as *not addressed*, which is what rule 2 commands
("absence is not falsehood").

So the 16.4% contradiction rate is not wrong, but it is **conditional on the
looser reading**. Under the strict evidence-only protocol the same population
would be called mostly `unknown`, and the filter would look far safer than it is
— while also being unable to catch the most common hallucination type, the
whole-cloth invented career.

## 4. What this run changes in Part 4

1. The truncation caveat can be closed: it is conservative, measured, and does
   not affect the conclusion.
2. A new limitation must be stated: run-to-run noise is about 12% on identical
   input, so differences of that size are not interpretable.
3. The contradiction rate needs its definition attached whenever it is quoted.
   "Contradicted" here means "the article asserts something incompatible", not
   "the article does not mention it".

## Caveats

- One model, one run per condition, 40 claims. The 12% noise figure therefore has
  wide uncertainty too, but it is a floor that cannot be argued away.
- Sixteen of the 40 claims had identical evidence in both conditions by
  construction; only 24 pairs test truncation.
- The 20 contradicted-at-support-1.0 claims are deliberately overrepresented, so
  no population rate can be read off this table.
- Per-claim annotations are in `private/part4_adjudication_comparison.json` and
  must never be shown to an evaluator.
