# Part 5 pilot artifacts

Everything here is exploratory. None of it is ground truth, and nothing under
`exp/results/` was modified.

| Path | Contents |
|---|---|
| `wikidata/` | Wikidata coverage pilot: raw records, script, summary |
| `llm_adjudication/` | blind adjudication packages and the protocol |
| `hpc/` | steps that must run on the cluster (B2 re-clustering, Package B inputs) |
| `build_packages.py` | builds the blind packages from committed inputs |
| `build_part4_package.py` | builds Package B once the cluster files arrive |

## Why this lives under exp/handoff/

It is received or generated evidence with its own provenance, not a result
produced by `run_result()`. `exp/handoff/` already holds teammate deliveries
archived byte-for-byte, so the same convention applies.

## Status

- Package A (FActScore, 80 claims) and the 12-claim pilot: **built**.
- Package B (Part 4, 40 claims): **blocked** on `cache/ext/clusters.jsonl` and
  `cache/ext/labels_wiki.jsonl`, which exist only on the cluster.
- Second evidence source: Wikidata pilot **done** (insufficient coverage);
  independent-publisher pilot **not started**.
