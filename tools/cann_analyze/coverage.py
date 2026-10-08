from __future__ import annotations

from typing import Any

from cann_analyze.catalog import repos as catalog_repos
from cann_analyze.paths import index_path
from cann_analyze.store import connect, index_source, list_snapshots

# Baseline membership is a catalog decision (`baseline: true` in catalogs/repos.json).
# A repo listed in the catalog but absent from the index is a known blind spot: logs
# from that component can only be resolved through the file:line embedded in the log.


def _per_repo(conn) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        "SELECT repo_id, COUNT(*) AS sites, COUNT(DISTINCT path) AS files,"
        " SUM(CASE WHEN func IS NULL OR func = '' THEN 1 ELSE 0 END) AS func_empty,"
        " SUM(CASE WHEN lang = 'cpp' THEN 1 ELSE 0 END) AS cpp"
        " FROM sites GROUP BY repo_id"
    )
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        sites = row["sites"] or 0
        func_empty = row["func_empty"] or 0
        out[row["repo_id"]] = {
            "sites": sites,
            "files": row["files"] or 0,
            "cpp_sites": row["cpp"] or 0,
            "func_empty": func_empty,
            "func_coverage": round(1 - (func_empty / sites), 4) if sites else 0.0,
        }
    return out


def _per_level(conn) -> dict[str, int]:
    return {
        row["level"] or "UNKNOWN": row["n"]
        for row in conn.execute("SELECT level, COUNT(*) AS n FROM sites GROUP BY level ORDER BY n DESC")
    }


def coverage_report(conn=None) -> dict[str, Any]:
    """What the current index actually covers, and which catalog repos it misses.

    Pass `conn` to report on an injected index (tests, overlays); otherwise the active
    index from `paths.index_path()` is used.
    """
    own = conn is None
    db = index_path(write=False)
    conn = conn or connect()
    try:
        per_repo = _per_repo(conn)
        snapshots = list_snapshots(conn)
        source = index_source(conn)
        levels = _per_level(conn)
    finally:
        if own:
            conn.close()

    catalog = catalog_repos()
    indexed = set(per_repo)
    baseline = [rid for rid, repo in catalog.items() if repo.get("baseline")]
    missing_baseline = sorted(rid for rid in baseline if rid not in indexed)
    catalog_only = sorted(rid for rid in catalog if rid not in indexed)

    total_sites = sum(v["sites"] for v in per_repo.values())
    total_empty = sum(v["func_empty"] for v in per_repo.values())
    return {
        "index_file": str(db) if db.is_file() else None,
        "index_source": source if db.is_file() else "missing",
        "schema": "cann-analyze.coverage.v1",
        "totals": {
            "repos_indexed": len(indexed),
            "repos_in_catalog": len(catalog),
            "repos_missing_from_index": len(catalog_only),
            "sites": total_sites,
            "cpp_sites": sum(v["cpp_sites"] for v in per_repo.values()),
            "func_empty": total_empty,
            "func_coverage": round(1 - (total_empty / total_sites), 4) if total_sites else 0.0,
        },
        "levels": levels,
        "per_repo": per_repo,
        "snapshots": snapshots,
        "blind_spots": {
            "baseline_not_indexed": missing_baseline,
            "catalog_not_indexed": catalog_only,
            "note": "Logs from these components resolve only via file:line embedded in the log; "
            "index them with: cann-analyze index --repo <id> --source <local clone>",
        },
    }
