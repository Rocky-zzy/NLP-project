import json

import pytest

import confqa.common.results as results


def test_writes_provenance_and_payload(tmp_path, monkeypatch):
    monkeypatch.setattr(results, "git_commit", lambda *a, **k: "deadbeef")
    monkeypatch.setattr(results, "git_dirty", lambda *a, **k: False)
    path = results.run_result(
        pipeline="conu",
        alpha=0.1,
        calib_frac=0.5,
        payload={"coverage": 0.9, "avg_set_size": 3.0},
        results_dir=tmp_path,
    )
    record = json.loads(path.read_text(encoding="utf-8"))
    assert path.name == "conu__a0.1__calib0.5.json"
    assert record["git"]["commit"] == "deadbeef"
    assert record["reportable"] is True
    assert record["coverage"] == 0.9
    assert record["alpha"] == 0.1


def test_dirty_tree_is_not_reportable(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(results, "git_dirty", lambda *a, **k: True)
    path = results.run_result(
        pipeline="conu",
        alpha=0.2,
        calib_frac=1.0,
        payload={"coverage": 0.8},
        results_dir=tmp_path,
    )
    record = json.loads(path.read_text(encoding="utf-8"))
    assert record["reportable"] is False
    assert "not reportable" in capsys.readouterr().err
    assert path.name == "conu__a0.2__calib1.json"


def test_reserved_keys_are_rejected(tmp_path):
    with pytest.raises(ValueError):
        results.run_result(pipeline="conu", payload={"reportable": True}, results_dir=tmp_path)


def test_config_hash_is_recorded(tmp_path):
    cfg = tmp_path / "c.yaml"
    cfg.write_text("seed: 0\n", encoding="utf-8")
    path = results.run_result(pipeline="fact", payload={"n": 1}, config=cfg, results_dir=tmp_path)
    record = json.loads(path.read_text(encoding="utf-8"))
    assert record["config"]["path"].endswith("c.yaml")
    assert len(record["config"]["sha256"]) == 64
