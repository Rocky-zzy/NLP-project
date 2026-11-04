import json

import pytest

pytest.importorskip("matplotlib")

from confqa.factuality.report import (
    GRID_ALPHAS,
    GRID_CALIB_FRACS,
    load_grid_results,
    plot_retention_vs_factuality,
)


def _record(alpha: float, fraction: float, retained: float, correct: float) -> dict:
    return {
        "pipeline": "fact",
        "reportable": True,
        "alpha": alpha,
        "calib_frac": fraction,
        "n_calibration": round(20 * fraction),
        "retention": retained,
        "retention_ci": [max(0.0, retained - 0.05), retained + 0.05],
        "all_correct_nonempty": correct,
        "all_correct_nonempty_ci": [max(0.0, correct - 0.1), min(1.0, correct + 0.1)],
        "empty_rate": 0.2,
        "empty_rate_ci": [0.1, 0.3],
        "_source_file": f"fact__a{alpha:g}__calib{fraction:g}.json",
    }


def _grid_records() -> list[dict]:
    return [
        _record(alpha, fraction, 0.2 + 0.05 * index, 0.6 + 0.03 * index)
        for index, (alpha, fraction) in enumerate(
            (alpha, fraction) for alpha in GRID_ALPHAS for fraction in GRID_CALIB_FRACS
        )
    ]


def test_plot_writes_png_and_pdf(tmp_path):
    png, pdf = plot_retention_vs_factuality(
        _grid_records(),
        png_path=tmp_path / "plot.png",
        pdf_path=tmp_path / "plot.pdf",
    )

    assert png.exists() and png.stat().st_size > 0
    assert pdf is not None and pdf.exists() and pdf.stat().st_size > 0


def test_load_real_grid_requires_all_six_cells():
    from confqa.common.paths import RESULTS

    if not any(RESULTS.glob("fact__a*__calib*.json")):
        pytest.skip("factuality grid results are not available")

    records = load_grid_results()

    assert len(records) == 6
    assert {(record["alpha"], record["calib_frac"]) for record in records} == {
        (alpha, fraction) for alpha in GRID_ALPHAS for fraction in GRID_CALIB_FRACS
    }
    assert all(record["reportable"] for record in records)


def test_load_grid_rejects_unreportable_result(tmp_path):
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    for record in _grid_records():
        path = results_dir / record["_source_file"]
        path.write_text(json.dumps(record), encoding="utf-8")
    bad = results_dir / "fact__a0.1__calib0.5.json"
    record = json.loads(bad.read_text(encoding="utf-8"))
    record["reportable"] = False
    bad.write_text(json.dumps(record), encoding="utf-8")

    with pytest.raises(ValueError, match="not reportable"):
        load_grid_results(results_dir)
