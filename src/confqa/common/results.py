"""Write one result json per experiment, stamped with provenance.

Every number in the report must come from one of these files. A file written
from a dirty working tree is marked reportable=False: it is fine for a quick
look, but it must not appear in the report.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path

from .paths import RESULTS

SCHEMA_VERSION = 1

RESERVED_KEYS = {
    "schema_version",
    "pipeline",
    "created_at",
    "elapsed_s",
    "git",
    "config",
    "model",
    "seed",
    "alpha",
    "calib_frac",
    "reportable",
}


def _git(args: Sequence[str], cwd: Path | None = None) -> str:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return ""
    if proc.returncode != 0:
        return ""
    return proc.stdout.strip()


def git_commit(cwd: Path | None = None) -> str:
    return _git(["rev-parse", "HEAD"], cwd) or "unknown"


def git_dirty(cwd: Path | None = None) -> bool:
    return bool(_git(["status", "--porcelain"], cwd))


def file_sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _default_name(pipeline: str, alpha: float | None, calib_frac: float | None) -> str:
    if alpha is None and calib_frac is None:
        return f"{pipeline}.json"
    alpha_part = "a" + ("none" if alpha is None else f"{alpha:g}")
    calib_part = "calib" + ("none" if calib_frac is None else f"{calib_frac:g}")
    return f"{pipeline}__{alpha_part}__{calib_part}.json"


def run_result(
    *,
    pipeline: str,
    payload: dict,
    alpha: float | None = None,
    calib_frac: float | None = None,
    config: str | Path | None = None,
    model: str | None = None,
    seed: int | None = None,
    name: str | None = None,
    results_dir: str | Path | None = None,
    elapsed_s: float | None = None,
) -> Path:
    """Write one result file and return its path.

    payload keys are merged at the top level, so it must not shadow the
    provenance fields.
    """
    clash = RESERVED_KEYS.intersection(payload)
    if clash:
        raise ValueError(f"payload uses reserved keys: {sorted(clash)}")

    directory = Path(results_dir) if results_dir is not None else RESULTS
    directory.mkdir(parents=True, exist_ok=True)

    dirty = git_dirty()
    record = {
        "schema_version": SCHEMA_VERSION,
        "pipeline": pipeline,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "elapsed_s": elapsed_s,
        "git": {"commit": git_commit(), "dirty": dirty},
        "config": None,
        "model": model,
        "seed": seed,
        "alpha": alpha,
        "calib_frac": calib_frac,
        "reportable": not dirty,
    }
    if config is not None:
        record["config"] = {
            "path": str(config),
            "sha256": file_sha256(config),
        }
    record.update(payload)

    path = directory / (name or _default_name(pipeline, alpha, calib_frac))
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if dirty:
        print(
            f"[run_result] WARNING: working tree is dirty; {path.name} is not reportable",
            file=sys.stderr,
        )
    return path
