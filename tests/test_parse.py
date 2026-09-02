from cann_analyze.parsers import parse_line


def test_slog_with_file_line():
    line = (
        "[ERROR] ASCENDCL(123,python):2026-09-02-18:11:41.121.000 "
        "[src/acl/aclrt_impl/context.cpp:244]create context failed, flags=1"
    )
    rec = parse_line(line)
    assert rec["parser"] == "slog"
    assert rec["level"] == "ERROR"
    assert rec["module"] == "ASCENDCL"
    assert rec["file"] == "src/acl/aclrt_impl/context.cpp"
    assert rec["line"] == 244
    assert "create context failed" in rec["msg"]


def test_event_level():
    line = (
        "[EVENT] ASCENDCL(123,python):2026-09-02-18:11:41.123.000 "
        "[src/acl/aclrt_impl/context.cpp:251]context created on device 0"
    )
    rec = parse_line(line)
    assert rec["level"] == "EVENT"
    assert rec["parser"] == "slog"


def test_msprof_python():
    line = "2026-09-02 18:11:41 [WARNING] [data_preparation_parser.py:104] - No data preparation data, data list is empty!"
    rec = parse_line(line)
    assert rec["parser"] == "msprof_py"
    assert rec["file"] == "data_preparation_parser.py"
    assert rec["line"] == 104
    assert rec["level"] == "WARNING"


def test_slog_strips_tid_and_func_prefix():
    rec = parse_line(
        "[ERROR] RUNTIME(171,python):2026-09-02-08:18:22.035.816 "
        "[profiling_agent.cc:620]171 ReportProfApi:Failed to report profiling API data, devId=5,ret=6"
    )
    assert rec["msg_body"].startswith("Failed to report profiling API data")
    assert "reportprofapi" not in rec["fingerprint"]


def test_slog_strips_tid_paren():
    rec = parse_line(
        "[ERROR] PROFILING(54308,):2026-09-02-21:18:32.052.517 "
        "[file_aging.cpp:61] (tid:54308) Available volume:0 (0MB) less than 20MB. Data will not be collected."
    )
    assert rec["msg_body"].startswith("Available volume")
    assert rec["file"] == "file_aging.cpp"


def test_torch_prof():
    line = "[2026-09-02-18:11:42.838] [WARNING] [AscendProfiler_ProfilingParser:86] 1 dequeue data match failed."
    rec = parse_line(line)
    assert rec["parser"] == "torch_prof"
    assert rec["file"] == "AscendProfiler_ProfilingParser"
    assert rec["line"] == 86
