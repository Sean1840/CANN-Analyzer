from __future__ import annotations

import json
import runpy
from functools import lru_cache
from pathlib import Path
from typing import Any

from cann_analyze.paths import catalogs_dir


def _load(name: str) -> dict[str, Any]:
    path = catalogs_dir() / name
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=8)
def repos() -> dict[str, dict[str, Any]]:
    data = _load("repos.json")
    return {item["id"]: item for item in data["repos"]}


@lru_cache(maxsize=8)
def modules() -> dict[str, list[str]]:
    return dict(_load("modules.json")["modules"])


@lru_cache(maxsize=8)
def log_macros() -> dict[str, Any]:
    return _load("log_macros.json")


@lru_cache(maxsize=8)
def msprof_signals() -> dict[str, Any]:
    return _load("msprof_signals.json")


@lru_cache(maxsize=8)
def loggers() -> dict[str, list[str]]:
    return dict(_load("loggers.json").get("names") or {})


@lru_cache(maxsize=8)
def return_codes() -> dict[str, Any]:
    return _load("return_codes.json")


def repo_by_id(repo_id: str) -> dict[str, Any]:
    table = repos()
    if repo_id not in table:
        raise KeyError(f"unknown repo id: {repo_id}")
    return table[repo_id]


def resolve_local_path(repo: dict[str, Any]) -> Path | None:
    raw = repo.get("local_path")
    if not raw:
        return None
    path = Path(raw)
    return path if path.exists() else None


def repos_for_module(module: str | None) -> list[str]:
    if not module:
        return []
    return list(modules().get(module.upper(), []))


def refresh_community() -> dict[str, Any]:
    """Refresh catalogs/community_repos.json from public GitCode org APIs. No token required."""
    script = Path(__file__).resolve().parents[2] / "scripts" / "fetch_community_repos.py"
    runpy.run_path(str(script), run_name="__main__")
    data = json.loads((catalogs_dir() / "community_repos.json").read_text(encoding="utf-8"))
    return {
        "script": str(script),
        "counts": {org: data["orgs"][org]["count"] for org in data.get("orgs", {})},
    }
