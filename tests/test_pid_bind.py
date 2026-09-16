from pathlib import Path

from cann_analyze.pid_bind import bind_pids, _norm


def test_norm_strips_zeros():
    assert _norm("02394278") == "2394278"


def test_bind_prof_and_plog_match(tmp_path: Path):
    prof = tmp_path / "PROF_000001_20260812102336309_02394278AQAABRAQ" / "host"
    prof.mkdir(parents=True)
    (prof / "info.json").write_text('{"pid":"2394278","pid_name":"python3"}', encoding="utf-8")
    (tmp_path / "plog.txt").write_text(
        "[INFO] PROFILING(2394278,python3):2026-08-12-10:23:36.000.000 [x.cpp:1] [1] hi\n",
        encoding="utf-8",
    )
    out = bind_pids(tmp_path)
    assert out["related"] is True
    assert "2394278" in out["plog"]["pids"]
    assert out["prof"][0]["pid"] == "2394278"


def test_bind_mismatch(tmp_path: Path):
    prof = tmp_path / "PROF_000001_20260812102336309_02394278AQAABRAQ" / "host"
    prof.mkdir(parents=True)
    (prof / "info.json").write_text('{"pid":"2394278"}', encoding="utf-8")
    (tmp_path / "plog.txt").write_text(
        "[INFO] GE(111,python3):2026-08-12-10:23:36.000.000 [x.cpp:1] [1] hi\n",
        encoding="utf-8",
    )
    out = bind_pids(tmp_path)
    assert out["related"] is False
    assert out["reason"] == "pid_mismatch"
