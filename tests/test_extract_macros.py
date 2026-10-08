"""Tests for the log-macro catalog and the macro shapes the extractor must handle.

msprof's own C++ layer (~1800 call sites) logs through bare ERROR/WARN/INFO/DEBUG and
PRINT_* macros. Those names were missing from catalogs/log_macros.json, so the bundled
index contained zero C++ sites for ascend/msprof and every "msprof parse failed ..."
question fell back to reading the source by hand.
"""

from __future__ import annotations

import json

from cann_analyze.extract import extract_c
from cann_analyze.paths import catalogs_dir


def _catalog_names() -> set[str]:
    data = json.loads((catalogs_dir() / "log_macros.json").read_text(encoding="utf-8"))
    return {item["name"] for item in data["c_macros"]}


def test_msprof_bare_logging_macros_are_in_the_catalog():
    names = _catalog_names()
    for name in ("ERROR", "WARN", "INFO", "DEBUG", "PRINT_ERROR", "PRINT_WARN", "PRINT_INFO"):
        assert name in names, f"{name} must be indexed: msprof C++ logs through it"


def test_bare_error_macro_is_extracted_with_level_and_fmt():
    text = (
        '#include "log.h"\n'
        "namespace Analysis\n"
        "{\n"
        "void ParseFailed(const std::string &path)\n"
        "{\n"
        '    ERROR("parse % failed, path is %", code, path);\n'
        "}\n"
        "}\n"
    )
    sites = extract_c(text, "analysis/csrc/demo.cpp")
    assert len(sites) == 1
    site = sites[0]
    assert site["macro"] == "ERROR"
    assert site["level"] == "ERROR"
    assert site["fmt"] == "parse % failed, path is %"
    assert site["path"] == "analysis/csrc/demo.cpp"
    assert site["line"] == 6


def test_macro_definition_line_is_not_a_site():
    text = (
        "#define ERROR(format, ...)                                    \\\n"
        "    Analysis::Utils::Log(LOG_ERROR, __FILE__, __LINE__, format, ##__VA_ARGS__)\n"
    )
    assert extract_c(text, "analysis/csrc/log.h") == []


def test_member_initializer_list_is_not_a_site():
    text = (
        "Event::Event(EventPtr eventPtr, const EventInfo &eventInfo)\n"
        "    : info(eventInfo), id(++g_eventIDCnt)\n"
        "{\n"
        "}\n"
    )
    assert extract_c(text, "analysis/csrc/event.cpp") == []


def test_qualified_call_is_not_attributed_to_the_bare_macro():
    text = "void F()\n{\n    obj::ERROR(1234);\n}\n"
    assert extract_c(text, "analysis/csrc/demo.cpp") == []


def test_bare_macros_do_not_double_count_a_prefixed_macro():
    """HCCL_ERROR must not also be indexed as a bare ERROR site."""
    text = 'void F()\n{\n    HCCL_ERROR("allreduce failed, ret=%d", ret);\n}\n'
    sites = extract_c(text, "src/hccl/demo.cpp")
    assert len(sites) == 1
    assert sites[0]["macro"] == "HCCL_ERROR"


def test_msprof_style_translation_unit_yields_every_level():
    """A file shaped like analysis/csrc code must yield ERROR/WARN/INFO/DEBUG sites."""
    text = (
        '#include "log.h"\n'
        "namespace Analysis\n"
        "{\n"
        "void Write(DataInventory &data)\n"
        "{\n"
        '    ERROR("write % failed", name);\n'
        '    WARN("record count is %", count);\n'
        '    INFO("write finished, count is %", count);\n'
        '    DEBUG("ctx is %", ctx);\n'
        "}\n"
        "}\n"
    )
    sites = extract_c(text, "analysis/csrc/domain/data_process/system/demo.cpp")
    assert [s["macro"] for s in sites] == ["ERROR", "WARN", "INFO", "DEBUG"]
    assert [s["level"] for s in sites] == ["ERROR", "WARNING", "INFO", "DEBUG"]
    assert all(s["path"] == "analysis/csrc/domain/data_process/system/demo.cpp" for s in sites)
    assert [s["line"] for s in sites] == [6, 7, 8, 9]
