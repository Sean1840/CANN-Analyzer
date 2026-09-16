from __future__ import annotations

import re
from typing import Any

from cann_analyze.catalog import loggers, msprof_signals, repos_for_module


def _hit_path(path: str | None, substrings: list[str]) -> bool:
    if not path:
        return False
    blob = path.replace("\\", "/")
    return any(s.replace("\\", "/") in blob for s in substrings)


def _hit_msg(msg: str | None, patterns: list[str]) -> bool:
    if not msg:
        return False
    return any(re.search(p, msg, re.I) for p in patterns)


def signals_for(record: dict[str, Any]) -> list[str]:
    spec = msprof_signals()
    hits: list[str] = []
    path = record.get("source_path") or record.get("file") or ""
    msg = record.get("msg") or ""
    module = (record.get("module") or "").upper()
    for name in ("collect", "parse", "unsupported", "component"):
        block = spec.get(name) or {}
        if _hit_path(path, block.get("path_substrings") or []):
            hits.append(name)
            continue
        if _hit_msg(msg, block.get("message_regex") or []):
            hits.append(name)
            continue
        if module and module in (block.get("modules") or []):
            hits.append(name)
    return list(dict.fromkeys(hits))


def candidate_repos(record: dict[str, Any]) -> list[str]:
    repos = repos_for_module(record.get("module"))
    path = (record.get("source_path") or "") + " " + (record.get("file") or "")
    lower = path.lower()
    name = record.get("file") or ""
    stem = name.rsplit(".", 1)[0] if name else ""
    for key, ids in loggers().items():
        if name == key or stem == key or key in name:
            for repo_id in ids:
                if repo_id not in repos:
                    repos.append(repo_id)
    if "msprof" in lower or "mindstudio_profiler" in lower or "parser.log" in lower:
        if "ascend/msprof" not in repos:
            repos.insert(0, "ascend/msprof")
    if "ascend/log" in lower.replace("\\", "/") or "plog-" in lower:
        if "cann/runtime" not in repos:
            repos.append("cann/runtime")
    return repos
