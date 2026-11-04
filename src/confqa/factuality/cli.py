"""Command-line entry points for the conformal-factuality pipeline."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from .cases import analyze_primary_cases
from .evaluate import DEFAULT_CONFIG, run_baseline, run_grid


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the B factuality pipeline.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    baseline = subparsers.add_parser("baseline", help="run the two-alpha baseline")
    baseline.add_argument("--config", default=str(DEFAULT_CONFIG))
    baseline.add_argument("--results-dir", default=None)

    grid = subparsers.add_parser("grid", help="run alpha by calibration-size grid")
    grid.add_argument("--config", default=str(DEFAULT_CONFIG))
    grid.add_argument("--results-dir", default=None)

    cases = subparsers.add_parser("cases", help="summarize failure-case candidates")
    cases.add_argument("--config", default=str(DEFAULT_CONFIG))

    args = parser.parse_args(argv)
    if args.command == "baseline":
        paths = run_baseline(args.config, results_dir=args.results_dir)
    elif args.command == "grid":
        paths = run_grid(args.config, results_dir=args.results_dir)
    elif args.command == "cases":
        analysis = analyze_primary_cases(args.config)
        print(
            f"alpha={analysis['alpha']} calib_frac={analysis['calib_frac']} "
            f"n_calibration={analysis['n_calibration']} "
            f"threshold={analysis['threshold']:.12f}"
        )
        print(f"summary={analysis['summary']}")
        print(f"cache_audit={analysis['cache_audit']}")
        return 0
    else:
        parser.error(f"unknown command: {args.command}")
        return 2

    for path in paths:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
