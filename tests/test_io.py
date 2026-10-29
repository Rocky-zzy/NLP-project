from confqa.common.io import load_config, read_jsonl, write_json, write_jsonl


def test_jsonl_roundtrip(tmp_path):
    rows = [{"a": 1, "b": "中文"}, {"a": 2}]
    p = tmp_path / "x.jsonl"
    assert write_jsonl(p, rows) == 2
    assert list(read_jsonl(p)) == rows


def test_load_config_json(tmp_path):
    p = tmp_path / "c.json"
    write_json(p, {"alpha": 0.1})
    assert load_config(p)["alpha"] == 0.1
