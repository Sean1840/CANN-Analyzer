import pytest

from cann_analyze.store import connect as real_connect


@pytest.fixture
def isolated_index(tmp_path, monkeypatch):
    db = tmp_path / "sites.sqlite"

    def _connect(path=None, **kwargs):
        # store.connect(path, *, write=False) is the real signature; index_cmd calls
        # connect(write=True). Accept and forward kwargs, but always route to the
        # temp db so tests never touch the shipped baseline or the user overlay.
        return real_connect(db, **kwargs)

    monkeypatch.setattr("cann_analyze.store.connect", _connect)
    monkeypatch.setattr("cann_analyze.index_cmd.connect", _connect)
    monkeypatch.setattr("cann_analyze.locate.connect", _connect)
    monkeypatch.setattr("cann_analyze.evidence.connect", _connect)
    return db
