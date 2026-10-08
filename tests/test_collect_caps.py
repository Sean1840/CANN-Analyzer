"""Tests for the inventory/caps contract of collect() and build_evidence().

Both are user-facing: a field dump that is too big to read must be reported, never
silently dropped; an evidence pack that stopped at a cap must say so.
"""

from __future__ import annotations

from cann_analyze.collect import MAX_LOG_BYTES, collect, text_log_paths
from cann_analyze.evidence import build_evidence
from cann_analyze.paths import project_root

FIXTURE_LOGS = project_root() / "fixtures" / "logs"


def test_collect_reports_no_skips_for_small_fixtures():
    inv = collect(FIXTURE_LOGS)
    assert inv["skipped"] == []
    assert inv["skipped_count"] == 0
    assert inv["limits"]["max_log_bytes"] == MAX_LOG_BYTES


def test_oversized_single_file_is_reported_not_dropped(tmp_path):
    big = tmp_path / "plog-big.log"
    big.write_text("[ERROR] RUNTIME(1,main):2026-09-02-18:11:41.121 [a.cpp:1] [tid:1] boom\n", encoding="utf-8")
    inv = collect(big, max_log_bytes=10)
    assert inv["file_count"] == 0
    assert inv["skipped_count"] == 1
    assert inv["skipped"][0]["reason"] == "too_large"
    assert inv["skipped"][0]["bytes"] == big.stat().st_size


def test_oversized_file_inside_directory_is_reported(tmp_path):
    (tmp_path / "small.log").write_text("hello\n", encoding="utf-8")
    big = tmp_path / "mindstudio_profiler_log"
    big.mkdir()
    (big / "Parser.log").write_text("x" * 500, encoding="utf-8")
    inv = collect(tmp_path, max_log_bytes=100)
    rels = {s["rel"] for s in inv["skipped"]}
    assert "mindstudio_profiler_log/Parser.log" in rels
    assert inv["file_count"] == 1


def test_missing_path_raises():
    import pytest

    with pytest.raises(FileNotFoundError):
        collect(project_root() / "fixtures" / "does-not-exist")


def test_text_log_paths_only_returns_readable_logs(tmp_path):
    (tmp_path / "plog-0.log").write_text("x\n", encoding="utf-8")
    (tmp_path / "info.json").write_text("{}", encoding="utf-8")
    inv = collect(tmp_path)
    names = {p.name for p in text_log_paths(inv)}
    assert names == {"plog-0.log"}


def test_evidence_reports_caps_and_no_silent_truncation(tmp_path):
    log = tmp_path / "plog-0.log"
    lines = [
        f"[ERROR] RUNTIME({1000 + i},main):2026-09-02-18:11:41.121 [context.cpp:{80 + i}] [tid:{1000 + i}] failed ret=507015"
        for i in range(30)
    ]
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")

    pack = build_evidence(tmp_path, max_records=5, locate_limit=1)
    assert pack["schema"] == "cann-analyze.evidence.v1"
    assert len(pack["records"]) == 5
    assert pack["caps"]["max_records"] == 5
    assert pack["caps"]["records"] == 5
    assert pack["caps"]["truncated"] is True
    assert pack["caps"]["records_available_before_cap"] >= 5
    assert pack["caps"]["candidate_log_files"] == 1
    assert pack["summary"]["record_count"] == 5


def test_evidence_not_truncated_when_everything_fits(tmp_path):
    log = tmp_path / "plog-0.log"
    log.write_text(
        "[ERROR] RUNTIME(1000,main):2026-09-02-18:11:41.121 [context.cpp:88] [tid:1000] failed ret=507015\n",
        encoding="utf-8",
    )
    pack = build_evidence(tmp_path, max_records=50)
    assert pack["caps"]["truncated"] is False
    assert len(pack["records"]) == 1
    assert pack["caps"]["log_files_scanned"] == 1


def test_evidence_surfaces_oversized_files_as_inventory_skips(tmp_path):
    log = tmp_path / "plog-huge.log"
    log.write_text("y" * 4096, encoding="utf-8")
    import cann_analyze.evidence as evidence_mod

    original = evidence_mod.collect

    def small_cap(path, **kwargs):
        return original(path, max_log_bytes=64)

    evidence_mod.collect = small_cap
    try:
        pack = build_evidence(tmp_path, max_records=10)
    finally:
        evidence_mod.collect = original
    assert pack["inventory"]["skipped_count"] == 1
    assert pack["records"] == []
