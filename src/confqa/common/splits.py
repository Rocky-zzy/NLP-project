"""Deterministic calibration / development / test splits.

A split file is built once, committed, and never regenerated. Every number in
the report must be traceable to one split file and its ids_sha256.

Design (agreed by the team, not dictated by the project brief):

- test is fixed and never touched by tuning;
- dev is a small disjoint slice used only to pick thresholds or prompts;
- the rest is a calibration pool, and the calibration-set-size factor
  subsamples that pool at a fraction in {0.5, 0.75, 1.0}.

Run once per dataset:

    python -m confqa.common.splits --dataset factscore \
        --annotations third_party/conformal-factual-lm/data/factscore_annotations.jsonl \
        --out data/splits/factscore.json

    python -m confqa.common.splits --dataset triviaqa --ids <ids.json|jsonl|txt> \
        --out data/splits/triviaqa.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections.abc import Sequence
from pathlib import Path

SCHEMA_VERSION = 1
DEFAULT_TEST_RATIO = 0.5
DEFAULT_DEV_RATIO = 0.1
DEFAULT_SEED = 0


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def make_split(
    ids: Sequence[str],
    *,
    test_ratio: float = DEFAULT_TEST_RATIO,
    dev_ratio: float = DEFAULT_DEV_RATIO,
    seed: int = DEFAULT_SEED,
) -> dict[str, list[str]]:
    """Split ids into disjoint test / dev / calib_pool lists.

    The result depends only on the *set* of ids, the ratios and the seed, so
    passing the same ids in a different order gives the same split.
    """
    unique = sorted(set(ids))
    if len(unique) < 3:
        raise ValueError("need at least 3 ids to build disjoint splits")
    if not 0.0 < test_ratio < 1.0:
        raise ValueError("test_ratio must be in (0, 1)")
    if not 0.0 <= dev_ratio < 1.0 - test_ratio:
        raise ValueError("dev_ratio leaves no room for the calibration pool")

    rng = random.Random(seed)
    shuffled = list(unique)
    rng.shuffle(shuffled)

    n = len(shuffled)
    n_test = max(1, int(round(n * test_ratio)))
    n_dev = max(0, int(round(n * dev_ratio)))
    if n_test + n_dev >= n:
        n_dev = max(0, n - n_test - 1)
    if n_test + n_dev >= n:
        n_test = n - n_dev - 1

    return {
        "test": sorted(shuffled[:n_test]),
        "dev": sorted(shuffled[n_test : n_test + n_dev]),
        "calib_pool": sorted(shuffled[n_test + n_dev :]),
    }


def build_split_file(
    dataset: str,
    ids: Sequence[str],
    *,
    source: str,
    source_sha256: str | None = None,
    test_ratio: float = DEFAULT_TEST_RATIO,
    dev_ratio: float = DEFAULT_DEV_RATIO,
    seed: int = DEFAULT_SEED,
    note: str | None = None,
) -> dict:
    """Build the full, self-describing split document that gets committed."""
    parts = make_split(ids, test_ratio=test_ratio, dev_ratio=dev_ratio, seed=seed)
    unique = sorted(set(ids))
    doc = {
        "schema_version": SCHEMA_VERSION,
        "dataset": dataset,
        "source": source,
        "source_sha256": source_sha256,
        "seed": seed,
        "test_ratio": test_ratio,
        "dev_ratio": dev_ratio,
        "n_total": len(unique),
        "ids_sha256": _sha256("\n".join(unique).encode("utf-8")),
        "counts": {key: len(value) for key, value in parts.items()},
        "splits": parts,
    }
    if note:
        doc["note"] = note
    return doc


def write_split(doc: dict, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def load_split(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_ids(path: str | Path) -> list[str]:
    """Read ids from a json list, a jsonl file with an id field, or plain text."""
    text = Path(path).read_text(encoding="utf-8").strip()
    if text.startswith("["):
        return [str(item) for item in json.loads(text)]

    ids: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("{"):
            record = json.loads(line)
            for key in ("qid", "id", "question_id"):
                if key in record:
                    ids.append(str(record[key]))
                    break
            else:
                raise ValueError(f"no id field in line: {line[:80]}")
        else:
            ids.append(line)
    return ids


def read_factscore_ids(path: str | Path) -> list[str]:
    """FActScore ids are positional: factscore-0000 is the first record in the file."""
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    records = data["data"] if isinstance(data, dict) else data
    return [f"factscore-{i:04d}" for i in range(len(records))]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a fixed, committed split file.")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--ids", help="json list / jsonl / one id per line")
    parser.add_argument("--annotations", help="FActScore annotation json")
    parser.add_argument("--out", required=True)
    parser.add_argument("--test-ratio", type=float, default=DEFAULT_TEST_RATIO)
    parser.add_argument("--dev-ratio", type=float, default=DEFAULT_DEV_RATIO)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--note", default=None, help="free-text caveat stored in the file")
    args = parser.parse_args(argv)

    if args.annotations:
        source = Path(args.annotations)
        ids = read_factscore_ids(source)
    elif args.ids:
        source = Path(args.ids)
        ids = read_ids(source)
    else:
        parser.error("one of --ids or --annotations is required")

    doc = build_split_file(
        args.dataset,
        ids,
        source=source.as_posix(),
        source_sha256=_sha256(source.read_bytes()),
        test_ratio=args.test_ratio,
        dev_ratio=args.dev_ratio,
        seed=args.seed,
        note=args.note,
    )
    out = write_split(doc, args.out)
    print(f"wrote {out}")
    print(f"  n_total={doc['n_total']} counts={doc['counts']}")
    print(f"  ids_sha256={doc['ids_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
