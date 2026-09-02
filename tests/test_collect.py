from cann_analyze.collect import collect
from cann_analyze.paths import project_root
from cann_analyze.stage_signals import signals_for
from cann_analyze.parsers import parse_line


def test_collect_fixtures():
    inv = collect(project_root() / "fixtures" / "logs")
    assert inv["file_count"] >= 3
    kinds = {f["kind"] for f in inv["files"]}
    assert "text_log" in kinds or "slog" in kinds or "msprof_parse" in kinds


def test_parse_signal_on_parser_log_name():
    rec = parse_line(
        "2026-09-02 18:11:41 [WARNING] [data_preparation_parser.py:104] - No data preparation data, data list is empty!",
        source_path="mindstudio_profiler_log/collection_host.log",
    )
    sig = signals_for(rec)
    assert "parse" in sig
