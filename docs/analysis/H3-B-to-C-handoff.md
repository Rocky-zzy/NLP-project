# H3 Handoff: New-Response Claim Processing

## Status

- Owner: B
- Consumer: C
- Interface, parsers, aggregation, fake-client tests, and documentation are
  complete.
- Real vLLM/Qwen integration and C's independent execution remain pending
  because C has not started generation.

## Scope

H3 consumes C's generated responses and prepares the frequency baseline used by
the extension. It does four things:

1. split each response into claims;
2. judge every target claim against each comparison response as
   support/contradict/unrelated;
3. aggregate the judgments into frequency scores;
4. join human labels and emit the shared `FactResponse` shape used by the
   existing conformal calibration and filtering code.

H3 does not generate responses and does not replace C's semantic-clustering
extension.

## Input

Input file: `cache/ext_responses.jsonl`

```json
{
  "pid": "ext-0001",
  "prompt": "...",
  "responses": ["...", "...", "...", "...", "..."]
}
```

`load_ext_responses` requires exactly five non-empty responses per prompt and
rejects duplicate prompt IDs.

The small offline fixture is:

- `examples/h3/ext_responses.jsonl`

## Public API

The implementation is in `src/confqa/factuality/h3.py`.

| Function | Purpose |
|---|---|
| `load_ext_responses` | Validate C's five-response input |
| `parse_claim_output` | Strictly parse claim JSONL and code fences |
| `parse_judgment_output` | Strictly parse `+1/0/-1` judgments |
| `split_claims` | Call the model to decompose one response |
| `judge_claims` | Judge all target claims against one response |
| `run_h3` | Run the full batch and write four cache files |
| `build_fact_responses` | Join labels and reuse B's calibration code |

## Model-client contract

C should wrap the vLLM OpenAI-compatible client in this protocol:

```python
class ChatClient(Protocol):
    def complete(
        self,
        messages: Sequence[dict[str, str]],
        *,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 1000,
    ) -> str: ...
```

Minimal adapter:

```python
class VLLMChatClient:
    def __init__(self, client):
        self.client = client

    def complete(self, messages, *, model, temperature=0.0, max_tokens=1000):
        completion = self.client.chat.completions.create(
            model=model,
            messages=list(messages),
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return completion.choices[0].message.content
```

The adapter must return one string and must not silently repair malformed JSON.
Parsing and failure recording are handled by H3.

## Target/comparison policy

`run_h3` accepts explicit:

- `target_response_ids`
- `comparison_response_ids`

The default is to use all five responses as targets and all five as comparisons.
This matches the five-response budget and gives the extension all claims across
the five responses. A target response is included in its own comparison set, so
the normal self-support case should receive `+1`.

The frequency baseline and semantic-clustering extension must use exactly the
same target/comparison policy. They cannot use different budgets or different
targets.

For a cheaper development smoke, C may set `target_response_ids=(0,)`, but both
baseline and extension must then use the same restriction.

## Output files

`run_h3(...)` writes:

- `cache/ext_claims.jsonl`
- `cache/ext_judgments.jsonl`
- `cache/ext_baseline_scores.jsonl`
- `cache/ext_h3_failures.jsonl`

Formats are defined in `docs/reference/schemas.md`.

For the offline fixture with target response 0:

- split rows: 5;
- judgment rows: 1;
- baseline score rows: 1;
- claim 0 frequency score: 5;
- claim 1 frequency score: 2;
- claim 1 support rate: 0.6.

## Failure handling

- Every claim line must parse; a partially bad split output fails the whole
  response instead of silently retaining valid lines.
- Every comparison must return exactly one score for every target claim.
- Missing, duplicate, unknown, fractional, or out-of-range IDs/scores are
  parse errors.
- Split and judge failures are written to `ext_h3_failures.jsonl` with raw model
  output.
- A judge failure skips the affected target score row rather than producing a
  partial frequency score.

C should report:

- number of split failures / total response splits;
- number of judge failures / total target-comparison calls;
- final usable target rows.

## Human labels and calibration

H3 does not create `Y/N/S/U` labels. C must annotate the target claims used for
calibration and evaluation.

After decoding a labels mapping keyed by `(pid, target_response_id, cid)`, call:

```python
responses = build_fact_responses(score_rows, labels)
```

The returned data uses B's existing:

- `rank_score`
- `conformal_threshold`
- `retain_claims`

This prevents the extension from independently reimplementing calibration.

## Acceptance checks

Run the offline tests:

```bash
PYTHONPATH=src .venv/bin/pytest tests/test_factuality_h3.py -q
```

Expected:

- code-fence parsing passes;
- malformed partial JSONL fails;
- missing and duplicate judgment IDs fail;
- invalid/fractional scores fail;
- fake-client end-to-end aggregation passes;
- split failures are recorded;
- labels join to the shared `FactResponse` representation.

## Pending C-side checks

- Connect the real vLLM Qwen client.
- Generate exactly 50 prompts × 5 responses with a frozen prompt list.
- Run H3 on the real generated responses.
- Report real parse-failure rates; target is below 5%.
- Manually inspect 20 claim/response judgments.
- Run from a directory owned by C without B intervention.

