from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

from cann_analyze.catalog import log_macros
from cann_analyze.fingerprint import error_codes, fingerprint, keywords

C_EXTS = {".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".cu"}
PY_EXTS = {".py"}
SKIP_DIRS = {
    ".git",
    "__pycache__",
    "third_party",
    "opensource",
    "node_modules",
    ".venv",
    "build",
    "build_llt",
    "output",
    "test",
    "tests",
    ".pytest_cache",
}
MAX_FILE_BYTES = 2_000_000

STRING = re.compile(r'"(?:\\.|[^"\\])*"')
PY_STRING = re.compile(r'("""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')')
IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
PRI_MACRO = re.compile(r"PRI[diouxX](?:8|16|32|64|MAX|PTR|FAST(?:8|16|32|64))?")
FUNC_RE = re.compile(
    r"(?:^|\n)[^\n]*?\b([A-Za-z_][A-Za-z0-9_:]*)\s*\([^;{}]*\)\s*(?:const\s*)?\{",
    re.MULTILINE,
)


def _decode_c_string(literal: str) -> str:
    body = literal[1:-1]
    return bytes(body, "utf-8").decode("unicode_escape", errors="replace")


def _decode_py_string(literal: str) -> str:
    if literal.startswith(('"""', "'''")):
        return literal[3:-3]
    return literal[1:-1]


def _adjacent_c_strings(text: str, start: int) -> tuple[str, int]:
    parts: list[str] = []
    i = start
    n = len(text)
    while i < n:
        while i < n and text[i] in " \t\r\n\\":
            if text[i] == "\\" and i + 1 < n and text[i + 1] == "\n":
                i += 2
                continue
            i += 1
        if i + 1 < n and text[i : i + 2] == "//":
            nl = text.find("\n", i)
            i = n if nl < 0 else nl + 1
            continue
        if i + 1 < n and text[i : i + 2] == "/*":
            end = text.find("*/", i + 2)
            i = n if end < 0 else end + 2
            continue
        match = STRING.match(text, i)
        if match:
            parts.append(_decode_c_string(match.group(0)))
            i = match.end()
            continue
        pri = PRI_MACRO.match(text, i)
        if pri:
            parts.append("%")
            i = pri.end()
            continue
        break
    return "".join(parts), i


def _call_span(text: str, open_paren: int) -> int:
    depth = 0
    i = open_paren
    n = len(text)
    in_str = None
    while i < n:
        ch = text[i]
        if in_str:
            if ch == "\\" and i + 1 < n:
                i += 2
                continue
            if ch == in_str:
                in_str = None
            i += 1
            continue
        if ch in "\"'":
            in_str = ch
            i += 1
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return n


def _line_number(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def _enclosing_func(text: str, index: int) -> str | None:
    last = None
    for match in FUNC_RE.finditer(text[: index + 1]):
        last = match.group(1)
    if last in {"if", "for", "while", "switch", "catch"}:
        return None
    return last


def _c_macros() -> list[tuple[str, dict[str, Any]]]:
    items = log_macros().get("c_macros", [])
    return sorted(((item["name"], item) for item in items), key=lambda x: len(x[0]), reverse=True)


def extract_c(text: str, path: str) -> list[dict[str, Any]]:
    sites: list[dict[str, Any]] = []
    macros = _c_macros()
    i = 0
    n = len(text)
    while i < n:
        if not (text[i].isalpha() or text[i] == "_"):
            i += 1
            continue
        match = IDENT.match(text, i)
        if not match:
            i += 1
            continue
        name = match.group(0)
        meta = next((m for n_, m in macros if n_ == name), None)
        if meta is None:
            i = match.end()
            continue
        j = match.end()
        while j < n and text[j] in " \t\r\n":
            j += 1
        if j >= n or text[j] != "(":
            i = match.end()
            continue
        end = _call_span(text, j)
        call = text[j:end]
        fmt, _ = _adjacent_c_strings(call, 1)
        if not fmt:
            # dlog_error(MODULE, "fmt", ...) — skip first ident, take first string
            str_match = STRING.search(call)
            if str_match:
                fmt = _decode_c_string(str_match.group(0))
        if fmt:
            line_no = _line_number(text, i)
            source_line = text.splitlines()[line_no - 1].strip()
            if source_line.lstrip().startswith("#define"):
                i = end
                continue
            sites.append(
                _annotate_site(
                    {
                        "path": path,
                        "basename": Path(path).name,
                        "line": line_no,
                        "func": _enclosing_func(text, i),
                        "macro": name,
                        "level": meta.get("level", "UNKNOWN"),
                        "lang": "cpp",
                        "fmt": fmt.strip(),
                        "fingerprint": fingerprint(fmt),
                        "error_codes": error_codes(fmt),
                        "module_hint": meta.get("module_hint"),
                        "source_line": source_line[:240],
                    }
                )
            )
        i = end
    return sites


def _py_functions() -> list[tuple[str, dict[str, Any]]]:
    items = log_macros().get("python_functions", [])
    return sorted(((item["name"], item) for item in items), key=lambda x: len(x[0]), reverse=True)


_PY_CALL = re.compile(
    r"(?P<name>logging\.(?:debug|info|warning|error|critical)|"
    r"logger\.(?:debug|info|warning|error|critical)|"
    r"log\.(?:debug|info|warning|error|critical)|"
    r"(?<!\.)\b(?:warn|error|info)\b)\s*\(",
    re.MULTILINE,
)


def extract_python(text: str, path: str) -> list[dict[str, Any]]:
    table = {name: meta for name, meta in _py_functions()}
    sites: list[dict[str, Any]] = []
    for match in _PY_CALL.finditer(text):
        name = match.group("name")
        meta = table.get(name, {"level": "INFO"})
        end = _call_span(text, match.end() - 1)
        call = text[match.end() - 1 : end]
        str_match = PY_STRING.search(call)
        if not str_match:
            continue
        fmt = _decode_py_string(str_match.group(0)).strip()
        if not fmt:
            continue
        sites.append(
            _annotate_site(
                {
                    "path": path,
                    "basename": Path(path).name,
                    "line": _line_number(text, match.start()),
                    "func": _enclosing_func(text, match.start()),
                    "macro": name,
                    "level": meta.get("level", "INFO"),
                    "lang": "python",
                    "fmt": fmt,
                    "fingerprint": fingerprint(fmt),
                    "error_codes": error_codes(fmt),
                    "module_hint": meta.get("module_hint"),
                    "source_line": text.splitlines()[_line_number(text, match.start()) - 1].strip()[:240],
                }
            )
        )
    return sites


def _annotate_site(site: dict[str, Any]) -> dict[str, Any]:
    site["keywords"] = keywords(
        site.get("fmt"),
        extra=list(site.get("error_codes") or [])
        + [site.get("basename"), site.get("macro"), site.get("func"), site.get("module_hint")],
    )
    return site


def should_skip(path: Path, skip_globs: Iterable[str]) -> bool:
    posix = path.as_posix()
    parts = set(path.parts)
    if parts & SKIP_DIRS:
        return True
    for glob in skip_globs:
        pattern = glob.replace("\\", "/")
        if Path(posix).match(pattern) or Path(posix).as_posix().endswith(pattern.rstrip("*")):
            # pathlib match is against the whole path; also handle **
            continue
    from fnmatch import fnmatch

    for glob in skip_globs:
        if fnmatch(posix, glob.replace("\\", "/")) or fnmatch(posix, "*/" + glob.replace("\\", "/")):
            return True
        # prefix dir skip: tests/**
        if glob.endswith("/**"):
            prefix = glob[:-3]
            if f"/{prefix}/" in f"/{posix}/" or posix.startswith(prefix + "/"):
                return True
    return False


def extract_file(path: Path, repo_root: Path) -> list[dict[str, Any]]:
    if path.stat().st_size > MAX_FILE_BYTES:
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    rel = path.relative_to(repo_root).as_posix()
    ext = path.suffix.lower()
    if ext in C_EXTS:
        return extract_c(text, rel)
    if ext in PY_EXTS:
        return extract_python(text, rel)
    return []
