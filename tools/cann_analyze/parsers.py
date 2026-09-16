from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

from cann_analyze.fingerprint import error_codes, fingerprint, strip_slog_prefix

LEVELS = ("ERROR", "WARNING", "WARN", "INFO", "DEBUG", "EVENT", "CRITICAL", "TRACE")

# plog: [LEVEL] MODULE(pid,prog):时间 [src:line] [tid] message
SLOG = re.compile(
    r"^\[(?P<level>ERROR|WARNING|WARN|INFO|DEBUG|EVENT|TRACE)\]\s*"
    r"(?P<module>[A-Za-z][A-Za-z0-9_]*)\s*"
    r"\((?P<pid>\d+)\s*,\s*(?P<pname>[^)]*)\)\s*:\s*"
    r"(?P<ts>\d{4}-\d{2}-\d{2}-\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:\.\d+)?)\s*"
    r"(?:\[(?P<file>[^:\]]+):(?P<line>\d+)\]\s*)?"
    r"(?:\[(?P<tid>(?:tid[:\s]*)?[^\]]+)\]\s*)?"
    r"(?P<msg>.*)$"
)

# 2026-09-02 18:11:41 [INFO] [ms_multi_process.py:77] - message
MSPROF_PY = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?)\s+"
    r"\[(?P<level>ERROR|WARNING|WARN|INFO|DEBUG|CRITICAL)\]\s+"
    r"\[(?P<file>[^:\]]+):(?P<line>\d+)\]\s*-?\s*"
    r"(?P<msg>.*)$"
)

# [2026-09-02-18:11:41.121] [INFO] [AscendProfiler_ProfilingParser:97] message
TORCH_PROF = re.compile(
    r"^\[(?P<ts>\d{4}-\d{2}-\d{2}[- ]\d{2}:\d{2}:\d{2}(?:\.\d+)?)\]\s+"
    r"\[(?P<level>ERROR|WARNING|WARN|INFO|DEBUG|EVENT)\]\s+"
    r"\[(?P<file>[^:\]]+):(?P<line>\d+)\]\s*"
    r"(?P<msg>.*)$"
)

# [MSVP] style: [ts]  [LEVEL] [MSVP] [pid] [file:line] message
MSVP = re.compile(
    r"^\[(?P<ts>[^\]]+)\]\s+\[(?P<level>ERROR|WARNING|WARN|INFO|DEBUG)\]\s+"
    r"\[MSVP\]\s+\[\d+\]\s+\[(?P<file>[^:\]]+):(?P<line>\d+)\]\s*"
    r"(?P<msg>.*)$"
)

# printf test-mode RT_LOG: [ERROR][file:line]tid msg
BRACKET_FILE = re.compile(
    r"^\[(?P<level>ERROR|WARNING|WARN|INFO|DEBUG|EVENT)\]\[(?P<file>[^:\]]+):(?P<line>\d+)\]\s*(?P<msg>.*)$"
)

GENERIC_FILE = re.compile(
    r"(?P<file>[\w./\\-]+\.(?:c|cc|cpp|cxx|h|hpp|py|cu|ts|js)):?(?P<line>\d+)"
)

VERSION_HINT = re.compile(
    r"\b(?:CANN|cann)[ \-_/]?v?(\d+\.\d+(?:\.\d+)?(?:\.[A-Za-z0-9]+)?)\b"
)


def _norm_level(level: str | None) -> str | None:
    if not level:
        return None
    up = level.upper()
    if up == "WARN":
        return "WARNING"
    if up == "CRITICAL":
        return "ERROR"
    return up


def _record(**kwargs: Any) -> dict[str, Any]:
    msg = (kwargs.get("msg") or "").strip()
    body = strip_slog_prefix(msg)
    rec = {
        "level": _norm_level(kwargs.get("level")),
        "module": kwargs.get("module"),
        "pid": kwargs.get("pid"),
        "tid": kwargs.get("tid"),
        "process": kwargs.get("pname"),
        "ts": kwargs.get("ts"),
        "file": kwargs.get("file"),
        "line": int(kwargs["line"]) if kwargs.get("line") else None,
        "msg": msg,
        "msg_body": body,
        "fingerprint": fingerprint(body or msg),
        "error_codes": error_codes(msg),
        "parser": kwargs.get("parser"),
        "raw": kwargs.get("raw"),
        "source_path": kwargs.get("source_path"),
    }
    return rec


def parse_line(line: str, source_path: str | None = None) -> dict[str, Any]:
    raw = line.rstrip("\n")
    text = raw.strip()
    if not text:
        rec = _record(raw=raw, parser="empty", source_path=source_path, msg="")
        rec["empty"] = True
        return rec

    for regex, parser in (
        (SLOG, "slog"),
        (MSVP, "msvp"),
        (TORCH_PROF, "torch_prof"),
        (MSPROF_PY, "msprof_py"),
        (BRACKET_FILE, "bracket_file"),
    ):
        match = regex.match(text)
        if match:
            data = match.groupdict()
            return _record(raw=raw, parser=parser, source_path=source_path, **data)

    generic = GENERIC_FILE.search(text)
    level = None
    for candidate in LEVELS:
        if f"[{candidate}]" in text.upper() or text.upper().startswith(candidate):
            level = candidate
            break
    rec = _record(
        raw=raw,
        parser="generic" if generic else "plain",
        source_path=source_path,
        level=level,
        file=generic.group("file") if generic else None,
        line=generic.group("line") if generic else None,
        msg=text,
    )
    return rec


def parse_text(text: str, source_path: str | None = None) -> list[dict[str, Any]]:
    return [parse_line(line, source_path) for line in text.splitlines() if line.strip()]


def parse_file(path: Path) -> list[dict[str, Any]]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return parse_text(text, source_path=str(path))


def extract_version_hints(records: Iterable[dict[str, Any]]) -> list[str]:
    found: list[str] = []
    for rec in records:
        blob = " ".join(str(rec.get(k) or "") for k in ("msg", "raw", "source_path"))
        for match in VERSION_HINT.finditer(blob):
            if match.group(1) not in found:
                found.append(match.group(1))
    return found
