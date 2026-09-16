from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from cann_analyze.parsers import SLOG

# msprof_<pid>_<yyyymmddhhmmssfff>_ascend_pt  — pid may be unpadded
_ASCEND_PT = re.compile(r"(?:^|_)(\d+)_\d{14,}_ascend_pt$", re.I)
# PROF_000001_<time>_<8digitPid><hash>
_PROF_DIR = re.compile(r"^PROF_\d+_\d+_(\d{8})[A-Za-z0-9]+$", re.I)
_PLOG_PID = re.compile(
    r"^\[(?:ERROR|WARNING|WARN|INFO|DEBUG|EVENT|TRACE)\]\s*"
    r"[A-Za-z][A-Za-z0-9_]*\s*\((\d+)\s*,"
)


def _norm(pid: str | int | None) -> str | None:
    if pid is None or pid == "":
        return None
    s = str(pid).strip()
    if not s.isdigit():
        return None
    return str(int(s))


def _ascend_pt_pid(path: Path) -> dict[str, Any] | None:
    for p in [path] + list(path.parents):
        m = _ASCEND_PT.search(p.name)
        if m:
            return {"pid": _norm(m.group(1)), "from": "filename", "path": str(p)}
        if p.name.lower().endswith("ascend_pt"):
            return {"pid": None, "from": "filename_renamed", "path": str(p)}
    return None


def _info_json_pid(info: Path) -> str | None:
    try:
        data = json.loads(info.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return _norm(data.get("pid"))


def _prof_pids(root: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for info in root.rglob("info.json*"):
        if info.name.endswith(".done"):
            continue
        pid = _info_json_pid(info)
        if not pid or pid in seen:
            continue
        seen.add(pid)
        cann = None
        try:
            cann = json.loads(info.read_text(encoding="utf-8")).get("cannVersion")
        except (OSError, json.JSONDecodeError):
            pass
        out.append({"pid": pid, "from": "info.json", "path": str(info), "cannVersion": cann})
    if out:
        return out
    for p in root.rglob("*"):
        if p.is_dir() and _PROF_DIR.match(p.name):
            pid = _norm(_PROF_DIR.match(p.name).group(1))
            if pid and pid not in seen:
                seen.add(pid)
                out.append({"pid": pid, "from": "prof_dirname", "path": str(p)})
    return out


def _plog_pids(root: Path, limit_files: int = 20) -> dict[str, Any]:
    counts: dict[str, int] = {}
    nfiles = 0
    files = []
    if root.is_file():
        files = [root]
    elif root.is_dir():
        files = [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in {".log", ".txt"}]
    for path in files[:limit_files]:
        if path.stat().st_size > 80_000_000:
            continue
        nfiles += 1
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for line in text.splitlines():
            m = SLOG.match(line) or _PLOG_PID.match(line)
            if not m:
                continue
            pid = _norm(m.group("pid") if "pid" in m.groupdict() else m.group(1))
            if pid:
                counts[pid] = counts.get(pid, 0) + 1
    return {"pids": sorted(counts, key=lambda k: -counts[k]), "counts": counts, "files_scanned": nfiles}


def bind_pids(root: Path) -> dict[str, Any]:
    """Compare ascend_pt / PROF / plog pids. Mismatch → related=false, stop analysis."""
    root = root.resolve()
    pt = _ascend_pt_pid(root)
    prof = _prof_pids(root)
    plog = _plog_pids(root)

    sets: dict[str, set[str]] = {}
    if pt and pt.get("pid"):
        sets["ascend_pt"] = {pt["pid"]}
    if prof:
        sets["prof"] = {x["pid"] for x in prof if x.get("pid")}
    if plog.get("pids"):
        sets["plog"] = set(plog["pids"])

    comparable = {k: v for k, v in sets.items() if v}
    related = True
    reason = "single_source"
    if len(comparable) >= 2:
        inter = set.intersection(*comparable.values())
        related = bool(inter)
        reason = "overlap" if related else "pid_mismatch"

    return {
        "related": related,
        "reason": reason,
        "ascend_pt": pt,
        "prof": prof,
        "plog": plog,
        "note": "ascend_pt 文件名被改则无法从名字取 pid，默认用户给的文件是一套。"
        if pt and pt.get("from") == "filename_renamed"
        else None,
    }
