# FActScore input provenance

The B pipeline reads only the cached inputs shipped by the official
`conformal-factual-lm` repository; it does not call an API or sample a model.

## Pinned source

- Repository: `https://github.com/tatsu-lab/conformal-factual-lm`
- Commit: `6022b4c90c6580f524f123b0cb97bbb61ab621d1`
- Local ignored checkout: `third_party/conformal-factual-lm`

## Input files

| File | SHA-256 | Purpose |
|---|---|---|
| `data/factscore_annotations.jsonl` | `c097adf730c6ba365d5179b8002c0758588c24c4b30f4a77c1edb31f8029ddbc` | 50 prompts and 408 annotated claims |
| `out/factscore_subclaims_with_scores.jsonl` | `f296834632fbba05eab2d4e4d52056a898f6041ab0090c1239a1303e2f7bd385` | Claims with cached confidence scores and tie-breaking noise |
| `out/factscore_survey.json` | `71e364100d04a67e4b4a973faabd728cd1d4b991d416f9f00fd112fc7fc4fb06` | Original and filtered answers for the final 30 prompts |

All three files above are paths relative to the pinned upstream checkout.

## Validated shape

- Responses: 50
- Claims: 408
- Claims per response: minimum 4, maximum 13, mean 8.16
- Annotations: `Y=235`, `S=52`, `N=75`, `U=46`
- Correct annotations: `Y` and `S`
- Fixed split: `test=25`, `dev=5`, `calib_pool=20`

The files ending in `.jsonl` are actually single wrapped JSON documents
(`{"data": [...]}`), not one JSON object per line.

## Known limitations

- `factscore_annotations.jsonl` does not include the original response text.
- Only `out/factscore_survey.json` preserves original and filtered response text,
  and it covers only the final 30 prompts.
- Upstream parsing-failure logs were not archived. Any claim-extraction or merge
  failure that left no trace in the cached files is therefore unknown rather
  than recoverable.
