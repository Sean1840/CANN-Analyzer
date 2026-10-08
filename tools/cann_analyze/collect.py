from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from cann_analyze.pid_bind import bind_pids

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

# A single log above this size is reported as skipped instead of silently dropped.
MAX_LOG_BYTES = 50_000_000


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


def _is_candidate(path: Path) -> bool:
    return _is_log(path) or any(h in path.name for h in PROF_META)


def _iter_candidate_files(root: Path):
    """Deterministic walk that yields (path, size) for candidate files only."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            item = Path(dirpath) / name
            try:
                if not item.is_file() or not _is_candidate(item):
                    continue
                size = item.stat().st_size
            except OSError:
                continue
            yield item, size


def collect(path: Path, *, max_log_bytes: int = MAX_LOG_BYTES) -> dict[str, Any]:
    """Inventory log/meta files under `path`.

    Never writes and never copies binary payloads. Files larger than `max_log_bytes`
    are excluded but reported in `skipped`, so a downstream reader can tell the
    difference between "no such data" and "too large to read".
    """
    root = path.resolve()
    entries: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    if root.is_file():
        size = root.stat().st_size
        if size > max_log_bytes:
            skipped.append({"path": str(root), "rel": root.name, "bytes": size, "reason": "too_large"})
        else:
            entries.append(
                {
                    "path": str(root),
                    "rel": root.name,
                    "kind": _kind(root),
                    "bytes": size,
                }
            )
    elif root.is_dir():
        for item, size in _iter_candidate_files(root):
            if size > max_log_bytes:
                skipped.append(
                    {
                        "path": str(item),
                        "rel": item.relative_to(root).as_posix(),
                        "bytes": size,
                        "reason": "too_large",
                    }
                )
                continue
            entries.append(
                {
                    "path": str(item),
                    "rel": item.relative_to(root).as_posix(),
                    "kind": _kind(item),
                    "bytes": size,
                }
            )
    else:
        raise FileNotFoundError(str(root))

    kinds: dict[str, int] = {}
    for e in entries:
        kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
    return {
        "root": str(root),
        "file_count": len(entries),
        "kinds": kinds,
        "files": entries,
        "limits": {"max_log_bytes": max_log_bytes},
        "skipped": skipped,
        "skipped_count": len(skipped),
        "pid_bind": bind_pids(root),
    }


def text_log_paths(inventory: dict[str, Any]) -> list[Path]:
    out = []
    for item in inventory.get("files") or []:
        if item["kind"] in {"slog", "msprof_parse", "msprof_collect", "text_log"}:
            path = Path(item["path"])
            if path.suffix.lower() in LOG_SUFFIXES or _is_log(path):
                out.append(path)
    return out
