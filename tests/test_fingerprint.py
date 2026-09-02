from cann_analyze.extract import extract_c
from cann_analyze.fingerprint import fingerprint, token_overlap
from cann_analyze.locate import basename_variants


def test_printf_and_numbers_collapse():
    a = fingerprint("create context failed, flags=%u")
    b = fingerprint("create context failed, flags=1")
    assert a == b


def test_path_and_pid_do_not_dominate():
    a = fingerprint("Analysis data in /tmp/PROF_000001/host failed")
    b = fingerprint("Analysis data in /var/data/PROF_999/host failed")
    assert token_overlap(a, b) >= 0.5


def test_priu64_concat_extract_and_fingerprint():
    src = 'MSPROF_LOGE("Available volume:%" PRIu64 " (%lluMB) less than 20MB. Data will not be collected.", v);'
    sites = extract_c(src, "file_ageing.cpp")
    assert sites
    assert "will not be collected" in sites[0]["fmt"]
    log_fp = fingerprint("(tid:1) Available volume:0 (0MB) less than 20MB. Data will not be collected.")
    assert token_overlap(log_fp, sites[0]["fingerprint"]) >= 0.6


def test_aging_ageing_variants():
    names = basename_variants("file_aging.cpp")
    assert "file_ageing.cpp" in names
