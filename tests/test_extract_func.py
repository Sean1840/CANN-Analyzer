"""Enclosing-function detection tests.

The snippets under tests/fixtures_extract are annotated with an
"@expect-func:" marker on the line above every logging call. EXPECTED_FUNCS
below restates the same mapping explicitly so the table is independent of the
markers, EXPECTED_MISSES names the only call sites that deliberately have no
enclosing function, and the inline case tables cover the individual C++ and
Python constructs one by one.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cann_analyze.extract import C_EXTS, PY_EXTS, extract_c, extract_file, extract_python

CORPUS_DIR = Path(__file__).resolve().parent / "fixtures_extract"

# file name -> enclosing function of every logging call, in source order.
EXPECTED_FUNCS: dict[str, list[str | None]] = {
    # C++ constructs.
    "cpp_01_ctor_init_list.cpp": ["Session::Session"],
    "cpp_02_ctor_multiline_params.cpp": ["Device::Device"],
    "cpp_03_template_trailing_return.cpp": ["GatherValues"],
    "cpp_04_noexcept_override.cpp": ["Worker::Run", "Worker::Run"],
    "cpp_05_multiline_params_defaults.cpp": ["Configure"],
    "cpp_06_kr_braces_for_body.cpp": ["FileAgeing::Init2", "FileAgeing::Init2"],
    "cpp_07_namespace_switch.cpp": ["ConfigureMode", "ConfigureMode"],
    "cpp_08_try_catch.cpp": ["HandleFailure", "HandleFailure"],
    "cpp_09_lambda_in_function.cpp": ["SortItems", "SortItems"],
    "cpp_10_lambda_namespace_scope.cpp": [None],
    "cpp_11_dtor_operator.cpp": ["Buffer::~Buffer", "Buffer::operator=="],
    "cpp_12_preprocessor_header.h": ["IsLogEnabled"],
    # Python constructs.
    "py_01_async_def.py": ["collect_async"],
    "py_02_decorated_classmethod.py": ["build"],
    "py_03_nested_def.py": ["inner", "outer"],
    "py_04_module_level.py": [None],
    "py_05_multiline_call.py": ["process", "next_step"],
    "py_06_class_methods.py": ["__init__", "_parse_one", "_parse_one", None],
}

# The only fixtures allowed to contain a call site without an enclosing
# function, with the reason. Any other empty "func" is a regression.
EXPECTED_MISSES: dict[str, str] = {
    "cpp_10_lambda_namespace_scope.cpp": "lambda assigned in a statement at namespace scope",
    "py_04_module_level.py": "module level logging call outside any def",
    "py_06_class_methods.py": "call in a class body outside any def",
}

# Control-flow keywords must never be reported as a function name.
BOGUS_FUNCS = frozenset(
    {"if", "for", "while", "switch", "catch", "try", "else", "do", "return", "sizeof", "case", "default"}
)


def corpus_files() -> list[Path]:
    return sorted(p for p in CORPUS_DIR.iterdir() if p.suffix in C_EXTS | PY_EXTS)


def expected_markers(path: Path) -> dict[int, str | None]:
    """Map the line of a logging call to the value of its marker comment."""
    markers: dict[int, str | None] = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if "@expect-func:" in line:
            value = line.split("@expect-func:", 1)[1].strip()
            markers[number + 1] = None if value == "(none)" else value
    return markers


def test_corpus_expected_func_table():
    files = corpus_files()
    assert len(files) == len(EXPECTED_FUNCS), [p.name for p in files]
    for path in files:
        assert path.name in EXPECTED_FUNCS, path.name
        got = [site["func"] for site in extract_file(path, CORPUS_DIR)]
        assert got == EXPECTED_FUNCS[path.name], path.name


def test_corpus_markers_match_extracted_sites():
    for path in corpus_files():
        sites = extract_file(path, CORPUS_DIR)
        markers = expected_markers(path)
        assert len(sites) == len(markers), path.name
        for site in sites:
            assert site["line"] in markers, "%s:%d has no @expect-func marker" % (path.name, site["line"])
            assert site["func"] == markers[site["line"]], "%s:%d" % (path.name, site["line"])


def test_corpus_has_no_unexpected_empty_func():
    for path in corpus_files():
        sites = extract_file(path, CORPUS_DIR)
        empty_lines = [site["line"] for site in sites if not site["func"]]
        deliberately_empty = [value for value in EXPECTED_FUNCS[path.name] if value is None]
        if empty_lines:
            assert path.name in EXPECTED_MISSES, "%s has unexplained empty func at lines %s" % (path.name, empty_lines)
            assert len(empty_lines) == len(deliberately_empty), path.name
        else:
            assert path.name not in EXPECTED_MISSES, path.name
            assert not deliberately_empty, path.name


def test_corpus_never_attributes_control_flow_keywords():
    for path in corpus_files():
        for site in extract_file(path, CORPUS_DIR):
            assert (site["func"] or "") not in BOGUS_FUNCS, "%s:%d" % (path.name, site["line"])


CPP_CASES = [
    (
        "ctor_with_init_list",
        'class Device {\npublic:\n    Device();\n};\n\nDevice::Device() : id_(1), name_{nullptr} {\n'
        '    ACL_LOG_ERROR("init %d", id_);\n}\n',
        ["Device::Device"],
    ),
    (
        "template_with_trailing_return",
        "template <typename T>\nauto Gather(const std::vector<T>& in) -> std::vector<T> {\n"
        '    RT_LOG_DEBUG("size=%zu", in.size());\n    return in;\n}\n',
        ["Gather"],
    ),
    (
        "multiline_parameters",
        "void Configure(\n    const Options& options,\n    int flags)\n{\n"
        '    GELOGE("bad flags=%d", flags);\n}\n',
        ["Configure"],
    ),
    (
        "noexcept_qualifier",
        'void Worker::Run() const noexcept {\n    MSPROF_LOGI("run");\n}\n',
        ["Worker::Run"],
    ),
    (
        "lambda_inside_function",
        "void Sort(std::vector<int>& items)\n{\n"
        "    std::sort(items.begin(), items.end(), [](int lhs, int rhs) {\n"
        '        RT_LOG_WARNING("compare %d %d", lhs, rhs);\n'
        "        return lhs < rhs;\n    });\n}\n",
        ["Sort"],
    ),
    (
        "namespace_qualified_definition",
        'void ns::inner::Start(int mode)\n{\n    RT_LOG_INFO("mode %d", mode);\n}\n',
        ["ns::inner::Start"],
    ),
    (
        "kr_brace_with_if_body",
        'int Check(int value)\n{\n    if (value < 0) {\n        MSPROF_LOGE("negative %d", value);\n'
        "    }\n    return value;\n}\n",
        ["Check"],
    ),
    (
        "destructor_and_operator",
        'Buffer::~Buffer()\n{\n    DRV_INFO("buffer released");\n}\n\n'
        'bool Buffer::operator==(const Buffer& other) const\n{\n    DRV_INFO("compare");\n    return true;\n}\n',
        ["Buffer::~Buffer", "Buffer::operator=="],
    ),
    (
        "if_body_at_file_scope",
        'if (gReady) {\n    ACL_LOG_ERROR("ready");\n}\n',
        [None],
    ),
    (
        "for_body_at_file_scope",
        'for (int i = 0; i < 3; ++i) {\n    MSPROF_LOGI("i=%d", i);\n}\n',
        [None],
    ),
    (
        "while_body_at_file_scope",
        'while (gBusy) {\n    RT_LOG_INFO("busy");\n}\n',
        [None],
    ),
    (
        "switch_body_at_file_scope",
        'switch (gMode) {\n    default:\n        GELOGE("bad mode");\n        break;\n}\n',
        [None],
    ),
    (
        "try_catch_at_file_scope",
        'try {\n    ACL_LOG_INFO("attempt");\n} catch (const std::exception& e) {\n'
        '    ACL_LOG_ERROR("failed");\n}\n',
        [None, None],
    ),
    (
        "lambda_at_namespace_scope",
        'auto report = [](int code) {\n    PROF_ERROR("code %d", code);\n};\n',
        [None],
    ),
    (
        "bare_block_at_file_scope",
        '{\n    ACL_LOG_INFO("block");\n}\n',
        [None],
    ),
    (
        "call_in_global_initializer",
        'static int g_flags = Register(ACL_LOG_ERROR("register failed"), 0);\n',
        [None],
    ),
    (
        "template_default_arguments",
        'template <typename T = int, int N = 3>\nvoid Fill(T* out)\n{\n    RT_LOG_DEBUG("fill %d", N);\n}\n',
        ["Fill"],
    ),
    (
        "extern_c_block_with_guards",
        '#ifdef __cplusplus\nextern "C" {\n#endif\n\nvoid Init(int value)\n{\n    RT_LOG_INFO("init %d", value);\n}\n',
        ["Init"],
    ),
    (
        "raw_string_with_braces",
        'void Raw(void)\n{\n    const char* text = R"(a { b } c)";\n    ACL_LOG_INFO("raw ok");\n}\n',
        ["Raw"],
    ),
    (
        "attribute_before_declarator",
        '__attribute__((visibility("default"))) void Export(int value)\n{\n    GELOGE("export %d", value);\n}\n',
        ["Export"],
    ),
    (
        "function_pointer_parameter",
        'void Register(void (*cb)(int), int flags)\n{\n    DRV_INFO("register %d", flags);\n}\n',
        ["Register"],
    ),
    (
        "operator_call_and_index",
        'void A::operator()(int value) const\n{\n    DRV_INFO("call %d", value);\n}\n\n'
        'int A::operator[](int index) const\n{\n    DRV_INFO("index %d", index);\n    return index;\n}\n',
        ["A::operator()", "A::operator[]"],
    ),
    (
        "lambda_in_member_init_list",
        'Obj::Obj() : cb_{[](int x) { return x; }} {\n    MSPROF_LOGI("built");\n}\n',
        ["Obj::Obj"],
    ),
    (
        "macro_block_is_not_a_function",
        "#define CHECK(x)       \\\n    do {                \\\n        if (!(x)) {     \\\n            return;     \\\n"
        "        }               \\\n    } while (0)\n\nvoid Use(int value)\n{\n    CHECK(value);\n"
        '    GELOGE("bad %d", value);\n}\n',
        ["Use"],
    ),
    (
        "crlf_source",
        'void F(int value)\r\n{\r\n    if (value) {\r\n        ACL_LOG_ERROR("v=%d", value);\r\n    }\r\n}\r\n',
        ["F"],
    ),
    (
        "truncated_file_without_closing_brace",
        'void Truncated(int value)\n{\n    if (value) {\n        ACL_LOG_ERROR("v=%d", value);\n',
        ["Truncated"],
    ),
]

PY_CASES = [
    (
        "async_def",
        'import logging\n\nasync def collect(path):\n    logging.info("collecting %s", path)\n',
        ["collect"],
    ),
    (
        "decorated_method",
        'import logging\n\nclass Parser:\n    @classmethod\n    def build(cls, name):\n'
        '        logging.error("failed %s", name)\n',
        ["build"],
    ),
    (
        "nested_def",
        'import logging\n\ndef outer(flag):\n    def inner(value):\n        logging.warning("inner %s", value)\n'
        '        return value\n    logging.info("outer %s", flag)\n    return inner(flag)\n',
        ["inner", "outer"],
    ),
    (
        "module_level",
        'import logging\n\nlogging.warning("no context here")\n',
        [None],
    ),
    (
        "multiline_call_inside_def",
        'import logging\n\ndef process(items):\n    logging.error(\n        "failed for %d",\n        len(items),\n    )\n',
        ["process"],
    ),
    (
        "class_body_call",
        'import logging\n\nclass Parser:\n    if True:\n        logging.warning("class body")\n',
        [None],
    ),
    (
        "dedented_second_function",
        'import logging\n\ndef first():\n    logging.info("first")\n\n\ndef second():\n    logging.info("second")\n',
        ["first", "second"],
    ),
    (
        "one_line_def",
        'import logging\n\ndef f(): logging.error("one liner")\n',
        ["f"],
    ),
    (
        "tab_indentation",
        'import logging\n\nclass C:\n\tdef m(self):\n\t\tlogging.info("tabbed")\n',
        ["m"],
    ),
    (
        "crlf_source",
        'import logging\r\n\r\ndef f():\r\n    logging.warning("crlf")\r\n',
        ["f"],
    ),
    (
        "nested_class_method",
        'import logging\n\nclass A:\n    class B:\n        def m(self):\n            logging.info("nested class")\n',
        ["m"],
    ),
    (
        "lambda_body_has_no_name",
        'import logging\n\nhandler = lambda: logging.error("in lambda")\n',
        [None],
    ),
    (
        "unclosed_bracket_after_call",
        'import logging\n\ndef f(x):\n    logging.error("a %s", x)\n    return (1,\n',
        ["f"],
    ),
]


@pytest.mark.parametrize("name, code, want", CPP_CASES, ids=[case[0] for case in CPP_CASES])
def test_cpp_case(name, code, want):
    assert [site["func"] for site in extract_c(code, name + ".cpp")] == want


@pytest.mark.parametrize("name, code, want", PY_CASES, ids=[case[0] for case in PY_CASES])
def test_python_case(name, code, want):
    assert [site["func"] for site in extract_python(code, name + ".py")] == want


def test_case_tables_never_report_control_flow_keywords():
    for name, code, _ in CPP_CASES:
        for site in extract_c(code, name + ".cpp"):
            assert (site["func"] or "") not in BOGUS_FUNCS
    for name, code, _ in PY_CASES:
        for site in extract_python(code, name + ".py"):
            assert (site["func"] or "") not in BOGUS_FUNCS


def test_enclosing_func_helper_is_offset_based():
    from cann_analyze.extract import _enclosing_func

    code = 'void Report(int code)\n{\n    if (code) {\n        ACL_LOG_ERROR("code %d", code);\n    }\n}\n'
    offset = code.index("ACL_LOG_ERROR")
    assert _enclosing_func(code, offset) == "Report"
    assert _enclosing_func(code, 0) is None
