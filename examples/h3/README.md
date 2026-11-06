# H3 Offline Example

`ext_responses.jsonl` contains one prompt and five synthetic responses. The
tests use a fake LLM client to exercise the complete H3 path without a model:

```text
5 responses
→ 5 claim-splitting calls
→ one target response
→ 5 comparison judgments
→ frequency aggregation
→ failure/audit files
```

Run:

```bash
PYTHONPATH=src .venv/bin/pytest tests/test_factuality_h3.py -q
```

The fake claims are:

1. `The sky is blue.`
2. `Grass is green.`

For target response 0 and all five comparison responses:

- `The sky is blue.` is supported by all five:
  `frequency_score=5`, `support_rate=1.0`.
- `Grass is green.` has three supports, one contradiction, and one unrelated:
  `frequency_score=2`, `support_rate=0.6`.

This is an interface test, not a real model result.
