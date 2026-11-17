# Run 3 — GPT6-Luna on the stratified 20 of the 80

Second model, same protocol file, on 20 claims drawn from `factscore_80_blind.jsonl`
(5 per frequency-score stratum). DeepSeek Flash runs the full 80 separately, so
this run is the cross-model check, not the primary sample.

## Protocol adherence

| Check | Result |
|---|---|
| records returned | 20 / 20 |
| blind IDs match the 20 dispatched | 20 / 20 |
| quotes found verbatim in the supplied evidence | **21 / 21** |
| output distribution | supported 6, unknown 12, contradicted 2 |

## The finding that matters: our label mapping was wrong

The pilot compared `Y`→supported, `N`→contradicted, `U`→unknown and scored
7 / 10. The pilot happened to contain **no `N` claims**, so that mapping was
never exercised. This run does exercise it, and it fails:

| annotation | n | strict agreement (`N`→contradicted) |
|---|---:|---:|
| `Y` | 7 | 4 |
| `N` | 7 | 2 |
| `U` | 1 | 1 |
| `S` (excluded) | 5 | — |
| **comparable** | **15** | **7 / 15** |

Five of the seven `N` claims came back `unknown` (F033, F041, F045, F061, F077).
That is not a model error — it is the protocol working as designed. FActScore's
`N` means *the article does not support the claim*, which covers both "the
article contradicts it" and "the article is silent". The protocol forbids
treating silence as falsehood (rule 2), so `unknown` is the correct output
for most `N` claims.

Under a mapping that respects what FActScore actually encodes
(`N` counts as agreement for either `contradicted` or `unknown`):

| | value |
|---|---:|
| comparable | 15 |
| agreement | **12 / 15** |

The two claims where the article does contradict the claim (F065 birthplace,
F069 birth date) were both returned `contradicted`; the five silences were both
correctly and deliberately returned `unknown`.

## Where the adjudicator genuinely fails

Only one mode survives: a `Y` claim that the passage does not state.

| id | annotation | state | why |
|---|---|---|---|
| F001 | `Y` | unknown | birth date given, birthplace not |
| F021 | `Y` | unknown | coach role stated, "after retiring" ordering not |
| F053 | `Y` | unknown | portraits mentioned, the two named sitters not |

`Y` recovery: **4 / 7 = 57%**, against 6 / 9 = 67% in the 12-claim pilot.
Both are far below 1.0, and the direction is consistent: a paragraph does not
state everything that is true about a person.

## The `S` claims are not errors either

Five `S` claims: three returned `unknown`, two returned `supported`. The two
`supported` ones are worth reading, because neither is a hallucination:

- **F005** — the evidence is the *disambiguation page* `Carlos Alfonso may refer to:`,
  and the extracted "claim" is a meta-statement that the name is ambiguous. The
  passage does support that. The claim extractor, not the adjudicator, produced
  a non-factual claim here.
- **F017** — "known for exceptional skill in engraving", supported by "entitles him
  to rank with the ablest artists of his time". Defensible; the human marked it
  subjective because "known for" is evaluative.

## Consequences for the 80-claim batch

1. Do not report a single agreement rate. Report per annotation class: `Y`
   recovery, `N` treated as not-supported, `U`, and `S` excluded.
2. Reference the 12-claim pilot only for schema adherence and quote fidelity; its
   7 / 10 is **not** affected by the mapping problem, because it contained no
   `N` claims.
3. The evidence-based filter's ceiling is the `Y` recovery rate, currently
   57–67%. That is the number C's utility argument has to be made against.

## Caveats

- 20 claims, one model, one run, no repeat.
- The 20 are a subset of the 80, so the `Y` rate here is an early estimate, not
  the final figure.
- Per-claim annotations are in `private_id_mapping.json`; the files in this
  directory must never be shown to an evaluator.
