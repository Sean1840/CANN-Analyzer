import json

from cann_analyze import catalog as catalog_mod


def test_apply_local_paths_merges_and_leaves_unknown_ids(tmp_path, monkeypatch):
    overlay = tmp_path / "repos.local.json"
    overlay.write_text(
        json.dumps(
            {
                "local_paths": {"cann/runtime": str(tmp_path / "runtime")},
                "repos": [{"id": "missing/repo", "local_path": "/nope"}],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(catalog_mod, "catalogs_dir", lambda: tmp_path)
    table = {
        "cann/runtime": {"id": "cann/runtime", "url": "git://example/runtime"},
        "ascend/msprof": {"id": "ascend/msprof"},
    }
    out = catalog_mod._apply_local_paths(table)
    assert out["cann/runtime"]["local_path"] == str(tmp_path / "runtime")
    assert "local_path" not in out["ascend/msprof"]
    assert "missing/repo" not in out
    assert "local_path" not in table["cann/runtime"]
