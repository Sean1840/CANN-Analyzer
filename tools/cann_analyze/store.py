from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from cann_analyze.paths import index_path

SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY,
    repo_id TEXT NOT NULL,
    git_commit TEXT NOT NULL,
    ref TEXT,
    source_path TEXT,
    indexed_at TEXT NOT NULL,
    site_count INTEGER NOT NULL,
    UNIQUE(repo_id, git_commit)
);
CREATE TABLE IF NOT EXISTS sites (
    id INTEGER PRIMARY KEY,
    snapshot_id INTEGER NOT NULL,
    repo_id TEXT NOT NULL,
    git_commit TEXT NOT NULL,
    path TEXT NOT NULL,
    basename TEXT NOT NULL,
    line INTEGER NOT NULL,
    func TEXT,
    macro TEXT,
    level TEXT,
    lang TEXT,
    fmt TEXT,
    fingerprint TEXT,
    error_codes TEXT,
    module_hint TEXT,
    source_line TEXT
);
CREATE INDEX IF NOT EXISTS idx_sites_basename ON sites(basename);
CREATE INDEX IF NOT EXISTS idx_sites_fp ON sites(fingerprint);
CREATE INDEX IF NOT EXISTS idx_sites_repo ON sites(repo_id, git_commit);
CREATE INDEX IF NOT EXISTS idx_sites_level ON sites(level);
"""


def connect(path: Path | None = None) -> sqlite3.Connection:
    db = path or index_path()
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def latest_snapshot(conn: sqlite3.Connection, repo_id: str | None = None) -> dict[str, Any] | None:
    if repo_id:
        row = conn.execute(
            "SELECT * FROM snapshots WHERE repo_id=? ORDER BY indexed_at DESC LIMIT 1",
            (repo_id,),
        ).fetchone()
    else:
        row = conn.execute("SELECT * FROM snapshots ORDER BY indexed_at DESC LIMIT 1").fetchone()
    return dict(row) if row else None


def snapshot_for(conn: sqlite3.Connection, repo_id: str, commit: str | None) -> dict[str, Any] | None:
    if commit:
        row = conn.execute(
            "SELECT * FROM snapshots WHERE repo_id=? AND (git_commit=? OR git_commit LIKE ?)",
            (repo_id, commit, commit[:12] + "%"),
        ).fetchone()
        if row:
            return dict(row)
    return latest_snapshot(conn, repo_id)


def replace_snapshot(
    conn: sqlite3.Connection,
    repo_id: str,
    commit: str,
    ref: str | None,
    source_path: str,
    sites: Iterable[dict[str, Any]],
) -> int:
    now = datetime.now(timezone.utc).isoformat()
    existing = conn.execute(
        "SELECT id FROM snapshots WHERE repo_id=? AND git_commit=?",
        (repo_id, commit),
    ).fetchone()
    if existing:
        conn.execute("DELETE FROM sites WHERE snapshot_id=?", (existing["id"],))
        conn.execute("DELETE FROM snapshots WHERE id=?", (existing["id"],))
    cur = conn.execute(
        "INSERT INTO snapshots(repo_id, git_commit, ref, source_path, indexed_at, site_count) VALUES (?,?,?,?,?,0)",
        (repo_id, commit, ref, source_path, now),
    )
    snapshot_id = int(cur.lastrowid)
    rows = []
    for site in sites:
        rows.append(
            (
                snapshot_id,
                repo_id,
                commit,
                site.get("path"),
                site.get("basename"),
                int(site.get("line") or 0),
                site.get("func"),
                site.get("macro"),
                site.get("level"),
                site.get("lang"),
                site.get("fmt"),
                site.get("fingerprint"),
                json.dumps(site.get("error_codes") or []),
                site.get("module_hint"),
                site.get("source_line"),
            )
        )
    conn.executemany(
        """INSERT INTO sites(
            snapshot_id, repo_id, git_commit, path, basename, line, func, macro, level, lang,
            fmt, fingerprint, error_codes, module_hint, source_line
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        rows,
    )
    conn.execute("UPDATE snapshots SET site_count=? WHERE id=?", (len(rows), snapshot_id))
    conn.commit()
    return len(rows)


def list_snapshots(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return [dict(r) for r in conn.execute("SELECT * FROM snapshots ORDER BY repo_id, indexed_at DESC")]


def snapshot_map(conn: sqlite3.Connection) -> dict[tuple[str, str], dict[str, Any]]:
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for row in conn.execute("SELECT repo_id, git_commit, ref, indexed_at, source_path FROM snapshots"):
        out[(row["repo_id"], row["git_commit"])] = dict(row)
    return out


def search_sites(
    conn: sqlite3.Connection,
    *,
    fingerprint_value: str | None = None,
    basename: str | None = None,
    path_suffix: str | None = None,
    repo_ids: list[str] | None = None,
    level: str | None = None,
    commit: str | None = None,
    tokens: list[str] | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    clauses = []
    args: list[Any] = []
    if repo_ids:
        clauses.append(f"repo_id IN ({','.join('?' * len(repo_ids))})")
        args.extend(repo_ids)
    if basename:
        clauses.append("basename = ?")
        args.append(basename)
    if path_suffix:
        clauses.append("path LIKE ?")
        args.append("%" + path_suffix.replace("\\", "/"))
    if level:
        clauses.append("level = ?")
        args.append(level)
    if commit:
        clauses.append("(git_commit = ? OR git_commit LIKE ?)")
        args.extend([commit, commit[:12] + "%"])
    if fingerprint_value:
        clauses.append("(fingerprint = ? OR fingerprint LIKE ?)")
        args.extend([fingerprint_value, "%" + fingerprint_value[:40] + "%"])
    for tok in tokens or []:
        clauses.append("fingerprint LIKE ?")
        args.append("%" + tok + "%")
    where = " AND ".join(clauses) if clauses else "1=1"
    sql = f"SELECT * FROM sites WHERE {where} LIMIT ?"
    args.append(limit)
    return [dict(r) for r in conn.execute(sql, args)]
