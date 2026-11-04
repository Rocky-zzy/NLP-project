import json

import pytest

from confqa.common.splits import (
    build_split_file,
    load_split,
    main,
    make_split,
    write_split,
)

IDS = [f"q{i:03d}" for i in range(100)]


def test_split_is_deterministic_and_order_independent():
    first = make_split(IDS, seed=0)
    second = make_split(list(reversed(IDS)), seed=0)
    assert first == second


def test_split_parts_are_disjoint_and_cover_everything():
    parts = make_split(IDS, seed=0)
    test, dev, pool = set(parts["test"]), set(parts["dev"]), set(parts["calib_pool"])
    assert test & dev == set()
    assert test & pool == set()
    assert dev & pool == set()
    assert test | dev | pool == set(IDS)


def test_split_sizes_follow_ratios():
    parts = make_split(IDS, test_ratio=0.5, dev_ratio=0.1, seed=0)
    assert len(parts["test"]) == 50
    assert len(parts["dev"]) == 10
    assert len(parts["calib_pool"]) == 40


def test_different_seed_gives_different_split():
    assert make_split(IDS, seed=0) != make_split(IDS, seed=1)


def test_too_few_ids_is_rejected():
    with pytest.raises(ValueError):
        make_split(["a", "b"])


def test_ids_sha256_is_stable():
    a = build_split_file("demo", IDS, source="x")
    b = build_split_file("demo", list(reversed(IDS)), source="x")
    assert a["ids_sha256"] == b["ids_sha256"]
    assert a["counts"] == b["counts"]


def test_split_roundtrip(tmp_path):
    doc = build_split_file("demo", IDS, source="x")
    path = write_split(doc, tmp_path / "demo.json")
    assert load_split(path) == doc


def test_cli_builds_split_from_json_list(tmp_path):
    ids_file = tmp_path / "ids.json"
    ids_file.write_text(json.dumps(IDS), encoding="utf-8")
    out = tmp_path / "split.json"
    assert main(["--dataset", "demo", "--ids", str(ids_file), "--out", str(out)]) == 0
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["n_total"] == 100
    assert doc["counts"]["test"] == 50
