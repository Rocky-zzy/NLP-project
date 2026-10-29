"""Canonical repository paths.

Everything resolves from the repository root, never from the current working
directory, so scripts behave the same on a laptop and on the cluster.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA = REPO_ROOT / "data"
CACHE = REPO_ROOT / "cache"
RESULTS = REPO_ROOT / "exp" / "results"
FIGURES = REPO_ROOT / "figures"
CONFIGS = REPO_ROOT / "configs"


def ensure_dirs() -> None:
    """Create the directories that are ignored by git but written at run time."""
    for d in (CACHE, RESULTS, FIGURES):
        d.mkdir(parents=True, exist_ok=True)
