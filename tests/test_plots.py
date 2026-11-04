import pytest

pytest.importorskip("matplotlib")

from confqa.common.plots import plot_coverage_vs_size, plot_retention_vs_factuality

RECORDS = [
    {"alpha": 0.1, "avg_set_size": 3.0, "coverage": 0.90, "coverage_ci": [0.87, 0.93]},
    {"alpha": 0.1, "avg_set_size": 4.2, "coverage": 0.94, "coverage_ci": [0.91, 0.96]},
    {"alpha": 0.2, "avg_set_size": 1.8, "coverage": 0.82, "coverage_ci": [0.78, 0.86]},
    {"alpha": 0.1, "retention": 0.70, "all_correct_nonempty": 0.90},
    {"alpha": 0.2, "retention": 0.50, "all_correct_nonempty": 0.95},
]


def test_coverage_plot_is_written(tmp_path):
    out = plot_coverage_vs_size(RECORDS, tmp_path / "cov.png")
    assert out.exists() and out.stat().st_size > 0


def test_retention_plot_is_written(tmp_path):
    out = plot_retention_vs_factuality(RECORDS, tmp_path / "ret.png")
    assert out.exists() and out.stat().st_size > 0


def test_empty_input_does_not_crash(tmp_path):
    out = plot_coverage_vs_size([], tmp_path / "empty.png")
    assert out.exists()
