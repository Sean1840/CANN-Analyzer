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

# Enclosing function detection.
#
# Sites are attributed to the innermost *named* function that textually
# contains them. Anything that opens a scope without naming a function
# (if/for/while/switch/catch bodies, bare blocks, lambdas, class or namespace
# bodies) keeps the enclosing function of its parent scope, and a site with no
# enclosing function at all yields None instead of a bogus keyword.
#
# The scan is linear: literals, comments and preprocessor directives are
# blanked out first (same length, so offsets stay valid), delimiter pairs are
# collected in one pass, and every opening brace is classified with a bounded
# backward look at its header. Lookups are monotonic, so a whole file costs
# O(size) regardless of how many sites it holds.

_C_ESCAPED = r"\\[\s\S]"
_C_MASK_RE = re.compile(
    r"//[^\n]*"
    r"|/\*[\s\S]*?\*/"
    r'|(?:u8|u|U|L)?R"(?P<rdelim>[^ ()\\\t\r\n]{0,16})\([\s\S]*?\)(?P=rdelim)"'
    r'|(?:u8|u|U|L)?"(?:' + _C_ESCAPED + r'|[^"\\\n])*"'
    r"|(?:u8|u|U|L)?'(?:" + _C_ESCAPED + r"|[^'\\\n])*'"
    r"|^[ \t]*#[^\n]*(?:\\\n[^\n]*)*",
    re.MULTILINE,
)
_PY_MASK_RE = re.compile(
    r"#[^\n]*"
    r'|"""[\s\S]*?"""'
    r"|'''[\s\S]*?'''"
    r'|"(?:' + _C_ESCAPED + r'|[^"\\\n])*"'
    r"|'(?:" + _C_ESCAPED + r"|[^'\\\n])*'",
    re.MULTILINE,
)
_DELIM_RE = re.compile(r"[(){}]")
_C_KEYWORDS = frozenset(
    """
    alignas alignof and and_eq asm auto bitand bitor bool break case catch char
    char16_t char32_t class compl concept const consteval constexpr constinit
    const_cast continue co_await co_return co_yield decltype default delete do
    double dynamic_cast else enum explicit export extern false float for friend
    goto if inline int long mutable namespace new noexcept not not_eq nullptr
    operator or or_eq private protected public register reinterpret_cast
    requires return short signed sizeof static static_assert static_cast struct
    switch template this thread_local throw true try typedef typeid typename
    union unsigned using virtual void volatile wchar_t while xor xor_eq
    await def elif except finally from global import is lambda nonlocal pass
    raise with yield
    """.split()
)
_OP_SYM = (
    r"(?:\[\s*\]|\(\s*\)|->\*?|new(?:\s*\[\s*\])?|delete(?:\s*\[\s*\])?|co_await"
    r"|<=>|<<|>>|[-+*/%^&|~!=<>]+)"
)
_C_NAME_END_RE = re.compile(r"(?:operator\s*" + _OP_SYM + r"|~?[A-Za-z_]\w*)$")
_C_QUAL_RE = re.compile(r"(?:operator\s*" + _OP_SYM + r"|~?[A-Za-z_]\w*)\s*::\s*$")
_C_TAIL_WORD_RE = re.compile(
    r"(?:const|volatile|override|final|mutable|try)\b"
    r"|noexcept(?:\s*\([^;{}]*\))?"
    r"|throw(?:\s*\([^;{}]*\))?"
    r"|(?:__attribute__|__declspec|alignas)\s*\([^;{}]*\)"
    r"|&&|&"
)
_PY_DEF_RE = re.compile(r"^([ \t]*)(?:async[ \t]+)?def[ \t]+([A-Za-z_]\w*)[ \t]*\(", re.MULTILINE)

_NAME_WINDOW = 160
_PREFIX_WINDOW = 400
_MAX_PREV_PARENS = 12
_MAX_TAIL_CHARS = 1200


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


def _blank_literals(text: str, pattern: re.Pattern[str]) -> str:
    """Replace comments, string literals and directives with spaces.

    Newlines are preserved so the result has exactly the same length and line
    structure as the input, which keeps source offsets valid.
    """
    if not pattern.search(text):
        return text
    return pattern.sub(lambda match: re.sub(r"[^\n]", " ", match.group(0)), text)


def _skip_ws(text: str, index: int) -> int:
    while index < len(text) and text[index] in " \t\r\n":
        index += 1
    return index


def _c_operator_name(masked: str, end: int) -> tuple[str, int] | None:
    """Name of an operator()/operator[]/operator<sym> declarator ending at ``end``.

    Called only when the character before the parameter list cannot end a plain
    identifier: "]" and ")" belong to operator[]/operator(), symbol characters
    to the symbolic operators. A quick keyword check keeps lambdas and ordinary
    call expressions out of the window regex.
    """
    if masked.find("operator", max(0, end - 32), end) < 0:
        return None
    low = max(0, end - _NAME_WINDOW)
    window = masked[low:end]
    match = _C_NAME_END_RE.search(window)
    if match is None or match.end() != len(window):
        return None
    if match.group(0) == "operator" and masked.startswith("()", end):
        # operator() is part of the declarator name, not the parameter list.
        end += 2
        window = masked[low:end]
        match = _C_NAME_END_RE.search(window)
        if match is None or match.end() != len(window):
            return None
    start = low + match.start()
    while True:
        # Each step strictly moves left, so the whole qualified prefix is
        # consumed (ns::inner::Start, Buffer::~Buffer, Buffer::operator==, ...).
        low = max(0, start - _NAME_WINDOW)
        window = masked[low:start]
        qualifier = _C_QUAL_RE.search(window)
        if qualifier is None or qualifier.end() != len(window):
            break
        start = low + qualifier.start()
    name = "".join(masked[start:end].split())
    return (name, start) if name else None


def _c_name_before(masked: str, open_paren: int) -> tuple[str, int] | None:
    """Declarator name whose parameter list starts at ``open_paren``.

    Returns ``(name, start)`` with a namespace/class qualified name such as
    ``ns::Type::Type`` or ``Type::operator==``, or None when the parenthesis is
    not a parameter list (a call, a lambda, a control statement, ...). Plain
    identifiers are read with a character scan; operator declarators, which can
    contain punctuation, fall back to the window regex.
    """
    end = open_paren
    while end > 0 and masked[end - 1] in " \t\r\n":
        end -= 1
    if end == 0:
        return None
    previous = masked[end - 1]
    if previous.isalnum() or previous in "_~:":
        start = end
        while start > 0 and (masked[start - 1].isalnum() or masked[start - 1] in "_~:"):
            start -= 1
        name = masked[start:end]
        spaced_scope = start > 1 and masked[start - 1] in " \t" and "::" in masked[max(0, start - 8) : start]
        if name and not name.endswith("operator") and not spaced_scope:
            return name, start
    return _c_operator_name(masked, end)


def _c_prefix_ok(masked: str, start: int) -> bool:
    """Reject names that are really expressions, not declarations.

    A declarator is preceded by declaration specifiers and starts a statement
    or a block. An unmatched "(" or ")" (the name is a call argument),
    "=" (assignment), "." or "->" (member access) means the brace belongs to an
    expression such as a lambda passed to std::sort.
    """
    depth = 0
    angle = 0
    low = max(0, start - _PREFIX_WINDOW)
    i = start - 1
    while i >= low:
        ch = masked[i]
        if ch == ")":
            depth += 1
        elif ch == "(":
            if depth == 0:
                return False
            depth -= 1
        elif ch in ";{}":
            return depth == 0
        elif ch == ">":
            angle += 1
        elif ch == "<":
            if angle > 0:
                angle -= 1
        elif ch == ":":
            if i > 0 and masked[i - 1] == ":":
                i -= 1
            else:
                j = i - 1
                while j >= low and (masked[j].isalnum() or masked[j] == "_"):
                    j -= 1
                return masked[j + 1 : i] in {"public", "private", "protected", "default", "case"}
        elif depth == 0 and angle == 0:
            if ch in "=.,!?+-/%|^":
                return False
            if not (ch.isalnum() or ch in "_ \t\r\n[]~*&"):
                return False
        i -= 1
    return depth == 0


def _c_balanced_to(text: str, index: int, stop_colon: bool) -> int:
    """End of a balanced run, or -1 when it is not balanced.

    ``stop_colon`` also stops at a top level ":" that is not part of "::",
    which is where a member initializer list or trailing return type ends.
    """
    depth = 0
    n = len(text)
    i = index
    while i < n:
        ch = text[i]
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            if depth == 0:
                return -1
            depth -= 1
        elif ch == ";" and depth == 0:
            return -1
        elif ch == ":" and stop_colon and depth == 0:
            if i + 1 < n and text[i + 1] == ":":
                i += 1
            else:
                return i
        i += 1
    return i if depth == 0 else -1


def _c_tail_ok(tail: str) -> bool:
    """Whether the text between a parameter list and its "{" is a valid tail.

    The tail may hold cv/ref qualifiers, noexcept, attributes, a trailing
    return type and a member initializer list. The parameter list is validated
    separately by matching parentheses, so anything else (for example the
    arguments of an enclosing call) is rejected here.
    """
    if len(tail) > _MAX_TAIL_CHARS:
        return False
    n = len(tail)
    i = 0
    while True:
        i = _skip_ws(tail, i)
        match = _C_TAIL_WORD_RE.match(tail, i)
        if match is None:
            break
        i = match.end()
    if tail.startswith("->", i):
        i = _c_balanced_to(tail, i + 2, True)
        if i < 0:
            return False
        i = _skip_ws(tail, i)
    if i < n:
        if tail[i] != ":":
            return False
        i = _c_balanced_to(tail, i + 1, False)
        if i < 0:
            return False
    return tail[i:].strip() == ""


def _c_func_scopes(masked: str) -> list[tuple[int, int, str]]:
    """Spans ``(body_start, body_end, name)`` of every C/C++ function body."""
    paren_close: dict[int, int] = {}
    brace_close: dict[int, int] = {}
    paren_open: list[int] = []
    brace_open: list[int] = []
    paren_stack: list[int] = []
    brace_stack: list[int] = []
    for match in _DELIM_RE.finditer(masked):
        ch = match.group(0)
        at = match.start()
        if ch == "(":
            paren_stack.append(at)
            paren_open.append(at)
        elif ch == ")":
            if paren_stack:
                paren_close[paren_stack.pop()] = at
        elif ch == "{":
            brace_stack.append(at)
            brace_open.append(at)
        elif brace_stack:
            brace_close[brace_stack.pop()] = at
    scopes: list[tuple[int, int, str]] = []
    last = len(masked) - 1
    cursor = -1
    for brace in brace_open:
        while cursor + 1 < len(paren_open) and paren_open[cursor + 1] < brace:
            cursor += 1
        for index in range(cursor, max(-1, cursor - _MAX_PREV_PARENS), -1):
            if index < 0:
                break
            open_paren = paren_open[index]
            close = paren_close.get(open_paren)
            if close is None or close >= brace or brace - close > _MAX_TAIL_CHARS:
                continue
            found = _c_name_before(masked, open_paren)
            if found is None:
                continue
            name, start = found
            if name in _C_KEYWORDS:
                continue
            if not _c_tail_ok(masked[close + 1 : brace]):
                continue
            if not _c_prefix_ok(masked, start):
                continue
            close_brace = brace_close.get(brace)
            if close_brace is not None:
                # A body brace immediately followed by ",", ")" or "]" is a
                # braced initializer such as "retry_{3},`, not a function body.
                after = _skip_ws(masked, close_brace + 1)
                if after < len(masked) and masked[after] in ",)]":
                    continue
            scopes.append((brace + 1, brace_close.get(brace, last), name))
            break
    return scopes


def _py_body_start(masked: str, open_paren: int) -> int | None:
    """Offset just after the ":" that ends a ``def`` header, or None."""
    depth = 0
    i = open_paren
    n = len(masked)
    while i < n:
        ch = masked[i]
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
            if depth == 0:
                j = i + 1
                while j < n:
                    nxt = masked[j]
                    if nxt == ":":
                        return j + 1
                    if nxt == "\n":
                        break
                    j += 1
                return None
        i += 1
    return None


def _py_body_end(masked: str, body_start: int, indent: int) -> int:
    """Offset where the body's indentation block ends (dedent or EOF)."""
    n = len(masked)
    newline = masked.find("\n", body_start)
    if newline < 0:
        return n
    pos = newline + 1
    while pos < n:
        line_end = masked.find("\n", pos)
        if line_end < 0:
            line_end = n
        line = masked[pos:line_end]
        stripped = line.strip()
        if stripped:
            width = len(line) - len(line.lstrip(" \t"))
            if len(line[:width].expandtabs(8)) <= indent:
                return pos
        pos = line_end + 1
    return n


def _py_func_scopes(masked: str) -> list[tuple[int, int, str]]:
    """Spans ``(body_start, body_end, name)`` of every Python function body.

    Nested defs are reported innermost first, which is what an enclosing
    function lookup wants.
    """
    scopes: list[tuple[int, int, str]] = []
    for match in _PY_DEF_RE.finditer(masked):
        indent = len(match.group(1).expandtabs(8))
        body_start = _py_body_start(masked, match.end() - 1)
        if body_start is None:
            continue
        scopes.append((body_start, _py_body_end(masked, body_start, indent), match.group(2)))
    return scopes


class _FuncIndex:
    """Maps a source offset to the innermost enclosing named function.

    Scopes are queried in increasing offset order by the extractors, so the
    active scope stack is maintained incrementally. Out-of-order lookups reset
    the cursor instead of producing a wrong answer.
    """

    def __init__(self, scopes: list[tuple[int, int, str]]) -> None:
        self._scopes = scopes
        self._cursor = 0
        self._stack: list[tuple[int, int, str]] = []
        self._last = -1

    def at(self, index: int) -> str | None:
        if index < self._last:
            self._cursor = 0
            self._stack.clear()
        self._last = index
        stack = self._stack
        while stack and stack[-1][1] <= index:
            stack.pop()
        scopes = self._scopes
        while self._cursor < len(scopes) and scopes[self._cursor][0] <= index:
            scope = scopes[self._cursor]
            self._cursor += 1
            if scope[1] > index:
                stack.append(scope)
        return stack[-1][2] if stack else None


class _LineCounter:
    """Line numbers for offsets that arrive in increasing order.

    Counting newlines from the start of the file for every site is quadratic on
    large sources, so the counter resumes from the previous lookup. An
    out-of-order lookup restarts from the beginning of the text.
    """

    __slots__ = ("_text", "_upto", "_newlines", "_last")

    def __init__(self, text: str) -> None:
        self._text = text
        self._upto = 0
        self._newlines = 0
        self._last = -1

    def line_at(self, index: int) -> int:
        if index < self._last:
            self._upto = 0
            self._newlines = 0
        self._last = index
        self._newlines += self._text.count("\n", self._upto, index)
        self._upto = index
        return self._newlines + 1


def _c_func_index(text: str) -> _FuncIndex:
    return _FuncIndex(_c_func_scopes(_blank_literals(text, _C_MASK_RE)))


def _py_func_index(text: str) -> _FuncIndex:
    return _FuncIndex(_py_func_scopes(_blank_literals(text, _PY_MASK_RE)))


def _enclosing_func(text: str, index: int) -> str | None:
    """Enclosing C/C++ function name for an offset (single-lookup helper)."""
    return _c_func_index(text).at(index)


def _c_macros() -> list[tuple[str, dict[str, Any]]]:
    items = log_macros().get("c_macros", [])
    return sorted(((item["name"], item) for item in items), key=lambda x: len(x[0]), reverse=True)


def extract_c(text: str, path: str) -> list[dict[str, Any]]:
    sites: list[dict[str, Any]] = []
    macros = _c_macros()
    func_index: _FuncIndex | None = None
    counter = _LineCounter(text)
    lines: list[str] | None = None
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
            # dlog_error(MODULE, "fmt", ...) - skip first ident, take first string
            str_match = STRING.search(call)
            if str_match:
                fmt = _decode_c_string(str_match.group(0))
        if fmt:
            line_no = counter.line_at(i)
            if lines is None:
                lines = text.splitlines()
            source_line = lines[line_no - 1].strip()
            if source_line.lstrip().startswith("#define"):
                i = end
                continue
            if func_index is None:
                func_index = _c_func_index(text)
            sites.append(
                _annotate_site(
                    {
                        "path": path,
                        "basename": Path(path).name,
                        "line": line_no,
                        "func": func_index.at(i),
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
    func_index: _FuncIndex | None = None
    counter = _LineCounter(text)
    lines: list[str] | None = None
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
        if func_index is None:
            func_index = _py_func_index(text)
        line_no = counter.line_at(match.start())
        if lines is None:
            lines = text.splitlines()
        sites.append(
            _annotate_site(
                {
                    "path": path,
                    "basename": Path(path).name,
                    "line": line_no,
                    "func": func_index.at(match.start()),
                    "macro": name,
                    "level": meta.get("level", "INFO"),
                    "lang": "python",
                    "fmt": fmt,
                    "fingerprint": fingerprint(fmt),
                    "error_codes": error_codes(fmt),
                    "module_hint": meta.get("module_hint"),
                    "source_line": lines[line_no - 1].strip()[:240],
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
