# Part 1c — Shared infrastructure, provenance and compute

The two branches in Sections 1a and 1b were built by different people on
different schedules. This section describes the shared machinery that keeps their
numbers comparable and traceable, and states what can and cannot be re-run from
the repository alone.

## Repository and shared package

All experiment code lives in one installable package, `confqa`, split by owner:
`conu/` for the short-form branch, `factuality/` for the long-form branch,
`extension/` for Part 4, and `common/` for the pieces they share. At runtime the
package needs only `numpy` and `pyyaml`; `matplotlib` is an optional development
dependency, and the GPU stack (`vllm`, `torch`, `transformers`) is kept out of the
package entirely so the cluster login node can run the test suite without CUDA.

Continuous integration runs on every push: `ruff check`, `ruff format --check`,
and `pytest` on Python 3.11. The suite has 55 tests and needs no model, no
network and no GPU; it covers the metric definitions, the split builders, the
result writer, the long-form grid and the Part 4 figure builder.

## Fixed splits

Both experiments partition a frozen list of ids before any model call, and both
split files are committed:

| Dataset | File | Partition | Seed |
|---|---|---|---|
| FActScore | [`data/splits/factscore.json`](../data/splits/factscore.json) | 25 test / 5 dev / 20 calibration pool | 0 |
| TriviaQA | [`data/splits/triviaqa_a3.json`](../data/splits/triviaqa_a3.json) | 250 test / 250 calibration, 100 development ids excluded, 3 few-shot ids | 0 |

The TriviaQA file records `selection_uses_model_outcomes: false`, so the
partition provably does not depend on how the model answered. Its sha256
(`8279e9d7…`) is the value recorded inside every short-form result file, and the
FActScore split carries an `ids_sha256` of its own. Copying either file and
recomputing the hash is enough to confirm that a reported number was produced on
the partition it claims.

## Provenance in every result file

Results are written by a single function, `confqa.common.results.run_result`,
which stamps each file with the schema version, the pipeline, a UTC timestamp,
the git commit, a dirty flag, the config path and its sha256, the model, the
seed, the target level and calibration fraction, and a `reportable` boolean. The
boolean is computed by asking git whether anything outside `exp/` is
uncommitted, so writing a result cannot invalidate its own provenance, while a
result produced on a dirty tree is marked and can be filtered out.

Twenty result files are committed — six short-form, six long-form and eight for
Part 4 — and every number in Sections 1a, 1b, 3a and 4 traces to one of them.
Deliveries from teammates are archived byte-for-byte under
[`exp/handoff/`](../exp/handoff/) together with their `SHA256SUMS`, so an
imported artifact can be distinguished from one this repository produced.

## Pinning

Nothing in the reported pipeline floats on a moving version.

- Upstream code: ConU at `c0c450e` and `conformal-factual-lm` at `6022b4c`, both
  recorded in [`docs/reference/upstream_versions.md`](../docs/reference/upstream_versions.md).
  `third_party/` is never edited; the one behavioural change we need — disabling
  ConU's eligibility filter — ships as a patch applied to a temporary copy.
- Scorer: `cross-encoder/stsb-roberta-large` at revision `2b12c2c0…`.
- Generator: Qwen2.5-14B-Instruct, with per-file sha256 checksums for the
  weights and tokenizer committed in
  [`docs/reference/qwen2.5-14b.sha256sums`](../docs/reference/qwen2.5-14b.sha256sums).
- Data: TriviaQA `rc.nocontext` and the FActScore cache are identified by hash;
  neither is redistributed, and both are documented in
  [`docs/reference/factscore-inputs.md`](../docs/reference/factscore-inputs.md).

## Execution

Generation ran against a single vLLM server exposing an OpenAI-compatible
endpoint on one 40 GB MIG slice of an A800, started by
[`scripts/start_vllm.sh`](../scripts/start_vllm.sh). The server was launched with
`--max-model-len 2048`, and that limit shaped the Part 4 pipeline: the grounded
relabelling prompt had to fit a 3,000-character Wikipedia extract and a 700-token
completion, and requests that exceeded the window came back as HTTP 400 and were
retried with half the extract.

Everything downstream of generation runs on CPU from cached scores. The
filtering audit (Section 2a), the six-cell calibration grid (Section 3a), the
1,000-draw resampling check, and the entire Part 4 comparison need no model, no
GPU and no network. The recorded cost is 12,720.5 s of generation and 1,666.1 s
of scoring — request times measured after server startup, about four hours
inside the twenty-hour budget, and not the platform's metered allocation, which
also covers model loading and idle time (Section 1a states this caveat).

## What can be reproduced, and what cannot

| Step | Runs from this repository | Needs |
|---|---|---|
| Test suite, CI | yes | Python and numpy |
| Long-form grid and its figures | yes | the upstream cache, cloned separately |
| Part 4 comparison figure | yes | eight committed result files |
| Short-form calibration grid | yes | the frozen score matrix, held with the team |
| Answer generation | no | one GPU, the pinned model, the frozen question ids |
| Claim labelling for Part 4 | no | the vLLM endpoint and the vendored Wikipedia extracts |

The repository therefore reproduces every number from cached intermediate
artefacts but not the model calls that produced those intermediates. That split
is deliberate: dataset text and model generations are large, licensed
differently, and are not redistributed in a public repository, while everything
needed to re-derive a reported number from them is committed and hash-pinned.
