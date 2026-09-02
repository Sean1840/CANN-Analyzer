from __future__ import annotations

import re

_PRINTF = re.compile(
    r"%(?:\d+\$)?[#0\- +]?(?:\d+|\*)?(?:\.(?:\d+|\*))?[hlL]?[diuoxXfFeEgGaAcspn%]|%"
    r"|PRI[diouxX](?:8|16|32|64|MAX|PTR)?"
)
_SLOG_PREFIX = re.compile(
    r"^(?:\(tid:\s*\d+\)\s*)?(?:\d+\s+)?(?:[A-Za-z_][\w:]+:\s*)?"
)
_HEX = re.compile(r"\b0x[0-9a-fA-F]+\b")
_NUM = re.compile(r"\b\d+(?:\.\d+)?\b")
_PATH = re.compile(r"(?:[A-Za-z]:)?(?:[/\\][\w.\-]+)+")
_UUID = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
_WS = re.compile(r"\s+")
_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")
_ERROR_CODE = re.compile(
    r"\b(?:ACL_ERROR_[A-Z0-9_]+|EE\d{4}|EH\d{4}|EL\d{4}|EK\d{4}|RT_[A-Z0-9_]+ERROR)\b"
)


def strip_slog_prefix(text: str) -> str:
    if not text:
        return ""
    return _SLOG_PREFIX.sub("", text.strip(), count=1).strip()


def fingerprint(text: str) -> str:
    if not text:
        return ""
    out = strip_slog_prefix(text.replace("\\n", " "))
    out = _PRINTF.sub("%", out)
    out = _UUID.sub("%", out)
    out = _HEX.sub("%", out)
    out = _PATH.sub("%", out)
    out = _NUM.sub("%", out)
    out = out.lower()
    out = re.sub(r"[^a-z0-9%_]+", " ", out)
    out = _WS.sub(" ", out).strip()
    return out[:240]


def tokens(text: str) -> list[str]:
    fp = fingerprint(text)
    return [m.group(0) for m in _TOKEN.finditer(fp)][:16]


def error_codes(text: str) -> list[str]:
    if not text:
        return []
    return list(dict.fromkeys(_ERROR_CODE.findall(text)))


def token_overlap(a: str, b: str) -> float:
    left = set(tokens(a))
    right = set(tokens(b))
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)
