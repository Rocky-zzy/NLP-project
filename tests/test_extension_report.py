import pytest

from confqa.extension.report import _count, load_extension_results


@pytest.fixture(scope="module")
def records():
    return load_extension_results()


def test_four_settings_are_loaded(records):
    # Eight result files exist; the loader returns one row per setting after
    # checking that both target levels agree.
    assert len(records) == 4
    pairs = {(record["label_set"], record["method"]) for record in records}
    assert pairs == {
        (label_set, method)
        for label_set in ("weak", "grounded")
        for method in ("baseline", "support")
    }


def test_counts_cover_every_response(records):
    for record in records:
        assert sum(record["counts"].values()) == record["n_responses"]


def test_grounded_cells_share_the_nonempty_correct_count(records):
    grounded = {r["method"]: r for r in records if r["label_set"] == "grounded"}
    assert grounded["baseline"]["counts"]["non_empty_correct"] == 2
    assert grounded["support"]["counts"]["non_empty_correct"] == 2
    assert grounded["baseline"]["counts"]["empty"] == 16
    assert grounded["support"]["counts"]["empty"] == 4


def test_retention_rises_with_support_in_both_label_sets(records):
    for label_set in ("weak", "grounded"):
        rows = {r["method"]: r for r in records if r["label_set"] == label_set}
        assert rows["support"]["retention"] > rows["baseline"]["retention"]


def test_non_integer_response_counts_are_rejected(tmp_path):
    path = tmp_path / "ext_baseline__a0.1.json"
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="whole number"):
        _count(0.5, 3, "empty_rate", path)
