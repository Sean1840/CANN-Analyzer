from __future__ import annotations

import os
import time
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from cann_analyze.catalog import repo_by_id, repos, resolve_local_path
from cann_analyze.extract import C_EXTS, PY_EXTS, SKIP_DIRS, extract_file, should_skip
from cann_analyze.gitutil import clone_or_update, head_commit, head_ref
from cann_analyze.paths import mirrors_dir
from cann_analyze.store import connect, list_snapshots, replace_snapshot


def _match_any(rel: str, globs: list[str]) -> bool:
    if not globs:
        return True
    posix = rel.replace("\\", "/")
    for glob in globs:
        g = glob.replace("\\", "/")
        if fnmatch(posix, g) or fnmatch(posix, g.removeprefix("**/")):
            return True
        if g.endswith("/**") and (posix.startswith(g[:-3] + "/") or posix == g[:-3]):
            return True
    return False


def iter_source_files(root: Path, repo: dict[str, Any]) -> list[Path]:
    include = list(repo.get("index_globs") or ["**/*"])
    skip = list(repo.get("skip_globs") or [])
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        rel_dir = Path(dirpath).relative_to(root).as_posix()
        keep = []
        for name in dirnames:
            if name in SKIP_DIRS:
                continue
            child = Path(dirpath) / name
            if should_skip(child, skip):
                continue
            keep.append(name)
        dirnames[:] = keep
        for name in filenames:
            path = Path(dirpath) / name
            try:
                if not path.is_file() or path.is_symlink():
                    continue
            except OSError:
                continue
            if path.suffix.lower() not in C_EXTS | PY_EXTS:
                continue
            rel = path.relative_to(root).as_posix()
            if should_skip(path, skip) or not _match_any(rel, include):
                continue
            files.append(path)
    return files


def index_repo(repo_id: str, source: Path | None = None, commit: str | None = None) -> dict[str, Any]:
    repo = repo_by_id(repo_id)
    root = Path(source) if source else resolve_local_path(repo)
    if root is None or not root.exists():
        raise FileNotFoundError(
            f"no local clone for {repo_id}. Set catalogs/repos.json local_path or pass --source. "
            "locate never clones."
        )
    git_commit = commit or head_commit(root) or "unknown"
    ref = head_ref(root) or ""
    files = iter_source_files(root, repo)
    sites: list[dict[str, Any]] = []
    t0 = time.time()
    for path in files:
        sites.extend(extract_file(path, root))
    conn = connect()
    try:
        count = replace_snapshot(conn, repo_id, git_commit, ref, str(root), sites)
    finally:
        conn.close()
    return {
        "repo_id": repo_id,
        "commit": git_commit,
        "ref": ref,
        "source": str(root),
        "files_scanned": len(files),
        "sites": count,
        "elapsed_s": round(time.time() - t0, 3),
    }


def index_all(only_local: bool = True) -> list[dict[str, Any]]:
    results = []
    for repo_id, repo in repos().items():
        local = resolve_local_path(repo)
        if only_local and local is None:
            continue
        results.append(index_repo(repo_id, local))
    return results


def mirror_path(repo: dict[str, Any]) -> Path:
    org = repo.get("org") or "unknown"
    name = repo.get("name") or repo["id"].replace("/", "_")
    return mirrors_dir() / org / name


def ensure_source(repo: dict[str, Any]) -> dict[str, Any]:
    local = resolve_local_path(repo)
    if local is not None:
        return {"ok": True, "path": local, "action": "local_path"}
    dest = mirror_path(repo)
    fetched = clone_or_update(repo["url"], dest)
    fetched["path"] = Path(fetched["path"])
    return fetched


def bootstrap(repo_ids: list[str] | None = None) -> list[dict[str, Any]]:
    """Shallow-clone missing catalog repos into data/mirrors, then index. Locate still never clones."""
    results = []
    selected = repo_ids or list(repos())
    for repo_id in selected:
        repo = repo_by_id(repo_id)
        fetched = ensure_source(repo)
        entry: dict[str, Any] = {"repo_id": repo_id, "fetch": {k: (str(v) if isinstance(v, Path) else v) for k, v in fetched.items()}}
        if not fetched.get("ok"):
            entry["error"] = "fetch_failed"
            results.append(entry)
            continue
        try:
            entry["index"] = index_repo(repo_id, source=Path(fetched["path"]))
        except Exception as exc:
            entry["error"] = str(exc)
        results.append(entry)
    return results


def status() -> dict[str, Any]:
    conn = connect()
    try:
        snaps = list_snapshots(conn)
    finally:
        conn.close()
    local = []
    for repo_id, repo in repos().items():
        path = resolve_local_path(repo)
        local.append(
            {
                "id": repo_id,
                "local_path": str(path) if path else None,
                "indexed": any(s["repo_id"] == repo_id for s in snaps),
            }
        )
    return {"snapshots": snaps, "repos": local}
