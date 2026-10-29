import math

from confqa.common.metrics import (
    avg_set_size,
    bootstrap_ci,
    coverage,
    summarize_coverage,
    summarize_factuality,
)


def test_coverage_basic():
    assert coverage([True, False, True, True]) == 0.75


def test_coverage_empty_is_nan():
    assert math.isnan(coverage([]))


def test_avg_set_size():
    assert avg_set_size([1, 2, 3]) == 2.0


def test_factuality_counts_empty_separately():
    records = [
        {"claims": [{"correct": True, "retained": True}, {"correct": False, "retained": False}]},
        {"claims": [{"correct": True, "retained": False}]},
        {"claims": [{"correct": False, "retained": True}]},
    ]
    s = summarize_factuality(records)
    assert s["n"] == 3
    assert s["empty_rate"] == 1 / 3
    assert s["all_correct_nonempty"] == 1 / 3
    assert s["retention"] == 0.5


def test_bootstrap_ci_degenerate():
    lo, hi = bootstrap_ci([1, 1, 1, 1], n_boot=200)
    assert lo == 1.0 and hi == 1.0


def test_summarize_coverage_keys():
    out = summarize_coverage([True, False], [2, 4])
    assert out["coverage"] == 0.5
    assert out["avg_set_size"] == 3.0
    assert len(out["coverage_ci"]) == 2
