from cann_analyze.extract import extract_file
from cann_analyze.index_cmd import index_repo
from cann_analyze.locate import locate_one
from cann_analyze.paths import project_root

MINI = project_root() / "fixtures" / "mini_repo"


def test_extract_cpp_and_python_sites():
    cpp = extract_file(MINI / "src" / "context.cpp", MINI)
    names = {s["macro"] for s in cpp}
    assert "ACL_LOG_ERROR" in names
    assert "ACL_LOG_EVENT" in names
    assert "RT_LOG_ERROR" in names
    py = extract_file(MINI / "src" / "ms_multi_process.py", MINI)
    msgs = " ".join(s["fmt"] for s in py)
    assert "No data preparation data" in msgs


def test_index_and_locate_embedded_and_drift(isolated_index):
    result = index_repo("cann/runtime", source=MINI, commit="deadbeef")
    assert result["sites"] >= 4

    hit = locate_one(
        "[ERROR] ASCENDCL(123,python):2026-09-02-18:11:41.121.000 "
        "[src/acl/aclrt_impl/context.cpp:244]create context failed, flags=1"
    )
    assert hit["embedded"]["file"].endswith("context.cpp")
    assert hit["locations"], hit
    top = hit["locations"][0]
    assert top["path"].endswith("context.cpp")
    assert "create context failed" in (top["fmt"] or "")

    drifted = locate_one(
        "[ERROR] ASCENDCL(9,python):2026-01-01-00:00:00.000.000 "
        "[src/acl/aclrt_impl/context.cpp:10]create context failed, flags=9"
    )
    assert drifted["locations"]
    assert drifted["locations"][0]["line"] != 10

    ageing = locate_one(
        "[ERROR] PROFILING(54308,):2026-09-02-21:18:32.052.517 "
        "[file_aging.cpp:61] (tid:54308) Available volume:0 (0MB) less than 20MB. Data will not be collected."
    )
    assert ageing["locations"], ageing
    assert ageing["locations"][0]["path"].endswith("file_ageing.cpp")
    assert "collect" in ageing["signals"]

    report = locate_one(
        "[ERROR] RUNTIME(171,python):2026-09-02-08:18:22.035.816 "
        "[profiling_agent.cc:620]171 ReportProfApi:Failed to report profiling API data, devId=5,ret=6"
    )
    assert report["locations"], report
    assert report["locations"][0]["path"].endswith("profiling_agent.cc")
    assert report["return_codes"]
    assert report["return_codes"][0]["name"] == "MSPROF_ERROR_UNINITIALIZE"
    assert report["basis"]["disclaimer"]
    assert "cann/runtime" in report["basis"]["disclaimer"]
