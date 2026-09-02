from __future__ import annotations

from pathlib import Path
from typing import Any

LOG_SUFFIXES = {".log", ".txt", ".out", ".err"}
LOG_NAME_HINTS = (
    "plog-",
    "device-",
    "host_start",
    "dev_start",
    "collection_",
    "msprof_analysis",
    "Parser.log",
    "slog",
    "dlog",
)
PROF_META = {"info.json", "sample.json", "profiler_info", "profiler_metadata.json", "analyse.done"}


def _is_log(path: Path) -> bool:
    name = path.name
    if path.suffix.lower() in LOG_SUFFIXES:
        return True
    return any(h in name for h in LOG_NAME_HINTS)


def _kind(path: Path) -> str:
    posix = path.as_posix().lower()
    name = path.name.lower()
    if "mindstudio_profiler_log" in posix or "parser.log" in name or "msprof_analysis" in name:
        return "msprof_parse"
    if "/prof_" in posix or "host_start" in name or "dev_start" in name:
        return "msprof_collect"
    if "ascend/log" in posix or name.startswith("plog-") or "/run/" in posix or "/debug/" in posix:
        return "slog"
    if path.suffix.lower() in LOG_SUFFIXES:
        return "text_log"
    return "other"


def collect(path: Path) -> dict[str, Any]:
    root = path.resolve()
    files: list[Path] = []
    if root.is_file():
        files = [root]
    elif root.is_dir():
        for item in root.rglob("*"):
            if item.is_file() and (_is_log(item) or any(h in item.name for h in PROF_META)):
                if item.stat().st_size > 50_000_000:
                    continue
                files.append(item)
    else:
        raise FileNotFoundError(str(root))

    entries = []
    for item in sorted(files):
        entries.append(
            {
                "path": str(item),
                "rel": str(item.relative_to(root) if root.is_dir() and item != root else item.name),
                "kind": _kind(item),
                "bytes": item.stat().st_size,
            }
        )
    kinds: dict[str, int] = {}
    for e in entries:
        kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
    return {
        "root": str(root),
        "file_count": len(entries),
        "kinds": kinds,
        "files": entries,
    }


def text_log_paths(inventory: dict[str, Any]) -> list[Path]:
    out = []
    for item in inventory.get("files") or []:
        if item["kind"] in {"slog", "msprof_parse", "msprof_collect", "text_log"}:
            if Path(item["path"]).suffix.lower() in LOG_SUFFIXES or item["kind"] != "other":
                if Path(item["path"]).suffix.lower() in LOG_SUFFIXES or _is_log(Path(item["path"])):
                    out.append(Path(item["path"]))
    return out
