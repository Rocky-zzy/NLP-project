# ConU HPC run sources (A1–A4)

This directory preserves the scripts for launching the local Qwen service
(A1), preparing and checking the development runs (A2), collecting the
frozen 500-question run (A3), and independently auditing the filtering rule
from its saved scores (A4). The nine A2–A4 Python files match the recorded
SHA-256 hashes. The A1 launcher and evidence collector use a caller-supplied
work directory in place of the original account-specific default.

For an authorized rerun, use a separate working copy on Linux. The archived
Python scripts locate `data/`, `cache/` and `third_party/ConU` relative to the
repository root and expect the environment, models, and launcher in sibling
directories. From that working copy's repository root, place the archived
sources where the scripts originally ran:

```sh
cp scripts/conu-hpc/a[234]_*.py .
mkdir -p patches ../scripts
cp scripts/conu-hpc/patches/conu-no-filter.patch patches/
cp scripts/conu-hpc/a1/start_vllm_a1.sh ../scripts/
```

The launcher takes `A1_ROOT` (the parent of the checkout in this layout).
`a2-requirements-lock.txt` records the Python 3.11 HPC environment for reference;
it is not a Windows install list. The [upstream versions](../../docs/reference/upstream_versions.md)
and [A workstream notes](../../docs/manuals/A-conu.md) describe the pinned
dependencies and inputs. A3 reuses A2's frozen setup and requires the private
run inputs and model weights; A4 also requires the saved A3 scores. For A4
against the original frozen run, retain its original launch script and cache.
The public copy of the launcher does not match the launch script checksum in
the original plan. The archived pilot split contains only IDs and split metadata.

For the report, use the [ConU sections](../../docs/analysis/A-conu-sections.md),
the [main result tables](../../docs/analysis/main-tables.md), and the
[A5 audit and resampling handoff](../../exp/handoff/a5_resampling/README.md).
The A6 [case exporter](../../src/confqa/conu/a6_cases.py) reads the separate
A3/A4 reproduction bundle; the [reviewed cases](../../docs/analysis/A-conu-cases.md)
are already in Git. Original dataset records, full model outputs, model weights,
and cluster logs are kept separately.
