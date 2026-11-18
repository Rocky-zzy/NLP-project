# Part 5 — Can an external evidence judge certify these claims?

> Research extension, beyond the four parts the brief asks for. It exists to test
> the weakest link in Part 4: the labels. Everything below is reproducible from
> `exp/handoff/part5-pilot/`.

## 5.1 The question

Part 4's conclusion rests on a label set produced by a retrieval-grounded judge
that saw only the first 3,000 characters of each article. Two objections follow
immediately, and they are the two a careful reader would raise:

1. **Truncation.** If the judge never saw the rest of the article, some claims
   labelled `absent` may simply have been out of view.
2. **Circularity.** The evidence and the judge came from the same cached
   Wikipedia extract, so the label and the evidence are not independent.

Neither can be settled by argument. Both can be settled by asking a judge that
sees the article text and nothing else — no database, no memory, no labels — and
by asking it twice under controlled conditions.

The extension therefore builds a blind adjudication protocol and uses it to
measure three quantities that Part 4 currently asserts without evidence: how
often a claim can be certified from its article at all, how stable the verdict
is, and how much the 3,000-character cap matters.

## 5.2 Protocol

The adjudicator receives one atomic claim and one evidence passage, and answers
what **that passage** says about **that claim**, in one of three states:

| state | meaning |
|---|---|
| `supported` | the passage states or clearly entails the whole claim |
| `contradicted` | a genuine incompatibility between passage and claim |
| `unknown` | the passage does not address the claim, or addresses only part of it |

Four rules do most of the work. Absence is not falsehood, so an article that never
mentions something yields `unknown` even when the reader is certain the claim is
false. Partial support is `unknown`, with the missing part named. Every quotation
must be copied verbatim from the passage. Present-tense claims are judged against
the passage's retrieval date and the caveat is recorded.

The last rule is also the cheapest validity check available: an adjudicator that
invents a quotation cannot pass it. Across the five runs below, **177 of 177
quotations** were found verbatim in the supplied evidence.

The evaluator never sees the FActScore annotation, the frequency score used by
the baseline, the tie-break noise, any prior judge's verdict, or the private
mapping. Sampling depends only on the frequency-score stratum, never on the
annotation. Protocol, schema and sampling are frozen in
`llm_adjudication/{adjudication_prompt.md,adjudication_schema.json,selection_manifest.json}`.

## 5.3 Design

| material | size | purpose |
|---|---|---|
| pilot | 12 claims, all 50 biographies | protocol shakedown before spending model time |
| batch | 80 claims, 20 per frequency stratum | primary sample |
| cross-model subset | 20 of the 80 | is the verdict a property of the protocol or of the model? |
| paired probe (Package B) | 40 Part 4 claims x 2 evidence conditions | isolate the 3,000-character cap |
| threshold sensitivity (B2) | 550 Part 4 claims | was 0.60 the wrong similarity threshold? |

The paired probe is the one that needs care. Each claim appears twice, once with
the extract cut at 3,000 characters and once whole. The two copies were never
dispatched in the same conversation: an adjudicator that met the same claim twice
in one context could copy its earlier answer and manufacture exactly the
agreement the probe exists to measure. Sixteen of the 40 claims have an extract
under 3,000 characters, so for those the two copies are byte-identical — which
turns them into a free test-retest check.

## 5.4 Runs

| run | model | items | records | quotes verbatim | repair needed |
|---|---|---:|---:|---:|---|
| pilot | DeepSeek Flash | 12 | 12 | 12 / 12 | 0 |
| pilot | GPT6-Luna | 12 | 12 | 11 / 11 | 0 |
| cross-model subset | GPT6-Luna | 20 | 20 | 21 / 21 | 0 |
| batch | DeepSeek Flash | 80 | 80 | 89 / 89 | 2 |
| paired probe | DeepSeek Flash | 80 | 80 | 44 / 44 | 0 |

No run left a gap or a duplicate `blind_id`. Two records in the batch (F002,
F009) put unescaped double quotes inside a prose field and do not parse as JSON;
the raw file keeps them untouched, a single documented repair is applied for
analysis, and the repair is recorded. That is the only deviation from a
verbatim archive.

## 5.5 Results

### (a) The label mapping was wrong

The pilot compared `Y`→supported, `N`→contradicted, `U`→unknown, and scored
7/10. The pilot contained **no `N` claims**, so the mapping was never exercised.
The 20-claim subset exercised it and failed: five of seven `N` claims came back
`unknown`.

That is the protocol working, not breaking. FActScore's `N` means *the article
does not support the claim*, which covers both contradiction and silence. Under a
mapping that respects what the label encodes, the subset scores **12/15** instead
of 7/15. The pilot's 7/10 is unaffected, because it contained no `N` claims.

### (b) Precision is high, coverage is not

On the 80-claim batch:

| | value |
|---|---:|
| precision of a `supported` verdict | **22 / 23 = 95.7%** |
| recall on claims a human called true | **22 / 38 = 57.9%** |
| agreement, `N` read as not-supported | 55 / 72 = 76.4% |
| agreement, strict `N`→contradicted | 40 / 72 = 55.6% |

The recovery rate is stable across three independent samples: 6/9 (67%) in the
pilot, 4/7 (57%) in the subset, 22/38 (58%) in the batch. It is a property of the
evidence, not of the sample.

**The consequence for Part 4 is a ceiling.** A better filter can push precision
toward the high nineties; it cannot lift coverage, because the 16 claims the
evidence never mentions are invisible rather than misjudged. No re-ranking of the
same evidence source will find them.

### (c) Two models, same protocol

On the 12 pilot claims the two models returned **identical states, 12/12**, with
the same confidence on 11 of 12. On the harder 20-claim subset they agreed on
**18/20**, and both disagreements are defensible readings rather than errors: a
disambiguation page read as support for a meta-claim, and an ordering inference
("became a coach after retiring") that one model drew and the other refused.

So the verdict is driven by the protocol, not by model idiosyncrasy. That is what
lets a single model carry the 80-claim batch.

### (d) The adjudicator is not deterministic

The paired probe's 16 byte-identical pairs are the cleanest test in the project,
and it fails **2 of 16 (87.5%)**:

| claim | truncated copy | full copy | disagreement |
|---|---|---|---|
| Tusa, "is an Italian archaeologist" | `supported` | `contradicted` | one read the past tense and the dates as temporally contradicting a present-tense claim; the other treated it as a historical occupation |
| Fernando, "is a defensive midfielder" | `contradicted` | `unknown` | one treated "goalkeeper" as incompatible; the other refused to contradict what the passage never mentions |

**The measurement floor is about 12%.** Any difference smaller than that — and
that includes the gap between the thresholds in (f) — is inside the adjudicator's
own noise at this sample size. This number is not in the paper we reproduce, and
it should be attached to every comparison this project makes.

### (e) Truncation is conservative, not inflationary

Of the 24 claims whose two copies genuinely differ, **one** changed verdict:

- X013 (`full`, 4,805 characters) returned `supported` on "Valpy produced public
  affairs documentaries"; X077 (`first_3000`) returned `unknown`.

The direction follows from the protocol's semantics. A `supported` or
`contradicted` verdict needs positive evidence inside the visible window, so
hiding text can only turn those into `unknown`. **The 3,000-character cap makes
Part 4's rates conservative.** The A4 audit's confound is closed, and it closes in
the report's favour.

### (f) The similarity threshold was not the problem either

Re-clustering the Part 4 claims at stricter cross-encoder thresholds:

| threshold | clusters | mean size | real claims at unanimous support | contradicted among them | rate |
|---:|---:|---:|---:|---:|---:|
| 0.60 | 227 | 2.42 | 304 | 50 | **16.4%** |
| 0.75 | 458 | 1.20 | 79 | 8 | 10.1% |
| 0.85 | 535 | 1.03 | 14 | 3 | 21.4% |
| 0.90 | 546 | 1.01 | 4 | 0 | 0.0% |

Coverage collapses first — 67% → 17% → 3% → 0.9% of the 452 real claims — while
the contradiction rate does not fall. Claims that all five samples agree on and
Wikipedia denies are agreements; no similarity threshold undoes an agreement. The
0.60 default was not producing the 16.4%: 0.75 leaves only 79 claims and the rate
barely moves, 0.85 leaves 14 and the estimate is noise.

### (g) The two protocols disagree about absence

The paired probe deliberately oversamples claims the grounded labels call
`contradicted`. Of those 21 claims, the evidence-only adjudicator recovers **3**
and calls 18 `unknown`, because an invented career ("Foppert was an NFL kicker")
is *not mentioned* by the article rather than *refuted* by it.

So the 16.4% is not wrong, but it is **conditional on a reading**: it counts "the
article asserts something incompatible" and "the article is silent about a
fabrication" as the same verdict. A strict evidence-only protocol gets 3 of 21 and
loses the ability to catch whole-cloth fabrication — the most common failure mode
in the generated biographies.

## 5.6 What the extension changes in Part 4

1. The truncation objection is answered, empirically and in the report's favour.
2. A new limitation is mandatory: run-to-run noise is about 12%, so small
   differences between methods or thresholds are not interpretable.
3. The contradiction rate must carry its definition whenever it is quoted.
4. The precision/coverage frontier acquires a measured point: when an evidence
   judge certifies a claim it is right about 96% of the time, and it certifies
   about 58% of what is true. That is the honest bound on what a better filter
   can buy, and it parallels the precision/coverage trade-off the conformal
   analysis makes explicit.

## 5.7 Limitations

- Small samples throughout. 12, 20 and 80 claims; the 12% noise figure is a floor
  with wide uncertainty of its own.
- The evidence is a cached article extract capped at 12,000 characters and
  retrieved on 2026-11-08, with no revision IDs. Twenty-five of the 80 extracts
  are under 2,000 characters, and for those `unknown` is the expected answer.
- Annotations were made in 2023; several claims are present-tense and the evidence
  is from 2026. Three disagreements trace to exactly that.
- One model carries the 80-claim batch; the second model saw only 20 claims.
- Two model runs is not a distribution. Nothing here estimates within-model
  variance beyond the single test-retest check.

## 5.8 Reproduction

```bash
# protocol, schema, packages, mapping
ls exp/handoff/part5-pilot/llm_adjudication/

# every run: raw output, metadata, validation record
ls exp/handoff/part5-pilot/llm_adjudication/runs/

# threshold sensitivity (CPU is enough; --device defaults to cuda:0)
bash exp/handoff/part5-pilot/hpc/recluster_and_compare.sh
```

Run metadata records the model as displayed by each harness, the date, the
protocol hash and the input hash. Decoding settings were not exposed by either
harness and are recorded as unknown rather than guessed.
