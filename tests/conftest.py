from pathlib import Path

import pytest

from cann_analyze.store import connect as real_connect


@pytest.fixture
def isolated_index(tmp_path, monkeypatch):
    db = tmp_path / "sites.sqlite"

    def _connect(path=None):
        return real_connect(db)

    monkeypatch.setattr("cann_analyze.store.connect", _connect)
    monkeypatch.setattr("cann_analyze.index_cmd.connect", _connect)
    monkeypatch.setattr("cann_analyze.locate.connect", _connect)
    monkeypatch.setattr("cann_analyze.evidence.connect", _connect)
    return db
