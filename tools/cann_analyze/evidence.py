from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cann_analyze.collect import collect, text_log_paths
from cann_analyze.locate import analysis_basis, locate_record
from cann_analyze.parsers import extract_version_hints, parse_file
from cann_analyze.store import connect, snapshot_map


def build_evidence(path: Path, max_records: int = 400, locate_limit: int = 3) -> dict[str, Any]:
    inventory = collect(path)
    conn = connect()
    records: list[dict[str, Any]] = []
    parsed_all: list[dict[str, Any]] = []
    try:
        snaps = snapshot_map(conn)
        for log_path in text_log_paths(inventory):
            parsed = parse_file(log_path)
            parsed_all.extend(parsed)
            for rec in parsed:
                if rec.get("empty"):
                    continue
                located = locate_record(rec, conn=conn, limit=locate_limit)
                located["source_path"] = str(log_path)
                records.append(located)
                if len(records) >= max_records:
                    break
            if len(records) >= max_records:
                break
    finally:
        conn.close()

    levels = Counter((r["parsed"].get("level") or "UNKNOWN") for r in records)
    modules = Counter((r["parsed"].get("module") or "-") for r in records if r["parsed"].get("module"))
    repos = Counter()
    unlocated = 0
    for r in records:
        locs = r.get("locations") or []
        if not locs and not r.get("embedded"):
            unlocated += 1
        for loc in locs[:1]:
            repos[loc["repo_id"]] += 1
    signals = Counter()
    for r in records:
        for s in r.get("signals") or []:
            signals[s] += 1

    merged_locs = []
    for r in records:
        merged_locs.extend(r.get("locations") or [])
    dummy = {"line": None, "file": None, "msg": " ".join(extract_version_hints(parsed_all))}
    basis = analysis_basis(dummy, merged_locs, snaps)
    refresh = any((r.get("basis") or {}).get("refresh_needed") for r in records)

    return {
        "schema": "cann-analyze.evidence.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input": str(path),
        "inventory": {
            "root": inventory["root"],
            "file_count": inventory["file_count"],
            "kinds": inventory["kinds"],
        },
        "version_hints": extract_version_hints(parsed_all),
        "basis": {
            **basis,
            "refresh_needed": refresh or basis.get("refresh_needed"),
        },
        "summary": {
            "record_count": len(records),
            "levels": dict(levels),
            "modules": dict(modules),
            "top_repos": dict(repos),
            "signals": dict(signals),
            "unlocated": unlocated,
        },
        "records": records,
    }
