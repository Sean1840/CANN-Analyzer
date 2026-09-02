from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from cann_analyze.catalog import return_codes
from cann_analyze.fingerprint import fingerprint, tokens, token_overlap
from cann_analyze.parsers import parse_file, parse_line, parse_text
from cann_analyze.stage_signals import candidate_repos, signals_for
from cann_analyze.store import connect, search_sites, snapshot_map

LINE_REFRESH_DELTA = 20

_RET_FIELD = re.compile(r"\b(?:ret|retCode|retcode)\s*=\s*(-?\d+)\b", re.I)


def _basename(path: str | None) -> str | None:
    if not path:
        return None
    return Path(path.replace("\\", "/")).name


def basename_variants(name: str | None) -> list[str]:
    if not name:
        return []
    variants = {name}
    swapped = name.replace("ageing", "aging").replace("Ageing", "Aging")
    variants.add(swapped)
    variants.add(swapped.replace("aging", "ageing").replace("Aging", "Ageing"))
    variants.add(name.replace("aging", "ageing").replace("Aging", "Ageing"))
    return [v for v in variants if v]


def decode_return_codes(text: str | None) -> list[dict[str, str]]:
    if not text:
        return []
    catalog = return_codes()
    enums = catalog.get("enums") or {}
    fields = catalog.get("message_fields") or {}
    found = []
    for match in _RET_FIELD.finditer(text):
        raw = match.group(1)
        enum_name = fields.get("ret") or "MsprofErrorCode"
        label = (enums.get(enum_name) or {}).get(raw)
        if label:
            found.append({"field": "ret", "value": raw, "name": label, "enum": enum_name})
    return found


def _score(record: dict[str, Any], site: dict[str, Any]) -> tuple[int, list[str]]:
    reasons: list[str] = []
    score = 0
    rec_fp = record.get("fingerprint") or fingerprint(record.get("msg") or "")
    site_fp = site.get("fingerprint") or ""
    rec_base = _basename(record.get("file"))
    site_base = site.get("basename")
    rec_line = record.get("line")
    site_line = site.get("line")

    if rec_fp and site_fp and rec_fp == site_fp:
        score += 50
        reasons.append("fingerprint_exact")
    else:
        overlap = token_overlap(rec_fp, site_fp)
        if overlap >= 0.6:
            score += int(30 * overlap)
            reasons.append(f"fingerprint_overlap:{overlap:.2f}")

    rec_bases = set(basename_variants(rec_base))
    if rec_base and site_base and site_base in rec_bases:
        score += 40
        reasons.append("basename" if site_base == rec_base else "basename_variant")
        rec_file = (record.get("file") or "").replace("\\", "/")
        if rec_file and site.get("path", "").endswith(rec_file):
            score += 20
            reasons.append("path_suffix")
        elif any(site.get("path", "").endswith(v) for v in rec_bases):
            score += 12
            reasons.append("path_variant")

    if rec_line and site_line:
        if rec_line == site_line:
            score += 20
            reasons.append("line_exact")
        elif abs(rec_line - site_line) <= 15:
            score += 10
            reasons.append("line_near")
        elif rec_base == site_base:
            reasons.append("line_drift")

    rec_level = record.get("level")
    if rec_level and rec_level == site.get("level"):
        score += 4
        reasons.append("level")

    rec_codes = set(record.get("error_codes") or [])
    try:
        import json

        site_codes = set(json.loads(site.get("error_codes") or "[]"))
    except Exception:
        site_codes = set()
    if rec_codes and rec_codes & site_codes:
        score += 15
        reasons.append("error_code")

    module = (record.get("module") or "").upper()
    hint = (site.get("module_hint") or "").upper()
    if module and hint and module == hint:
        score += 10
        reasons.append("module")

    return score, reasons


def _confidence(score: int) -> str:
    if score >= 80:
        return "high"
    if score >= 50:
        return "medium"
    if score >= 25:
        return "low"
    return "weak"


def analysis_basis(record: dict[str, Any], locations: list[dict[str, Any]], snaps: dict[tuple[str, str], dict[str, Any]] | None = None) -> dict[str, Any]:
    used: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    reasons: list[str] = []
    rec_line = record.get("line")
    if not locations:
        reasons.append("no_index_hit")
    for loc in locations[:1]:
        key = (loc.get("repo_id") or "", loc.get("commit") or "")
        meta = (snaps or {}).get(key) or {}
        if key not in seen and key[0]:
            seen.add(key)
            used.append(
                {
                    "repo_id": key[0],
                    "commit": key[1],
                    "ref": loc.get("ref") or meta.get("ref"),
                    "indexed_at": loc.get("indexed_at") or meta.get("indexed_at"),
                }
            )
        loc_line = loc.get("line")
        if rec_line and loc_line and abs(int(rec_line) - int(loc_line)) > LINE_REFRESH_DELTA:
            reasons.append(f"line_delta:{rec_line}->{loc_line}")
        if loc.get("line_drift") and "fingerprint_exact" not in (loc.get("reasons") or []):
            reasons.append("weak_match_with_drift")
        if "basename_variant" in (loc.get("reasons") or []):
            reasons.append("filename_variant")
    reasons = list(dict.fromkeys(reasons))
    return {
        "snapshots": used,
        "refresh_needed": bool(reasons),
        "refresh_reasons": reasons,
        "disclaimer": format_disclaimer(used, reasons),
    }


def format_disclaimer(snapshots: list[dict[str, Any]], reasons: list[str]) -> str:
    if not snapshots:
        return (
            "分析未命中版本化日志点索引，仅依据日志内嵌 file:line。"
            "请提供现场 CANN/组件版本或运行 index --bootstrap 后重新分析。"
        )
    parts = []
    for snap in snapshots:
        commit = (snap.get("commit") or "")[:12]
        ref = snap.get("ref") or "?"
        when = snap.get("indexed_at") or "?"
        parts.append(f"{snap.get('repo_id')} @ {commit} ({ref}), indexed_at={when}")
    text = "本结论基于以下索引快照：" + "；".join(parts) + "。"
    if reasons:
        text += (
            "索引与日志存在偏差（"
            + ", ".join(reasons)
            + "）。若现场版本与上述 commit 不一致，请提供 CANN 版本/仓 tag 后重新分析。"
        )
    else:
        text += "若现场软件版本与上述 commit 偏差较大，请提供版本信息后重新分析。"
    return text


def locate_record(record: dict[str, Any], conn=None, limit: int = 5) -> dict[str, Any]:
    own = conn is None
    conn = conn or connect()
    try:
        snaps = snapshot_map(conn)
        repos = candidate_repos(record)
        basename = _basename(record.get("file"))
        fp = record.get("fingerprint") or fingerprint(record.get("msg_body") or record.get("msg") or "")
        distinctive = [t for t in tokens(fp) if len(t) >= 5][:6]
        candidates: list[dict[str, Any]] = []
        seen: set[tuple] = set()
        queries: list[dict[str, Any]] = []
        for name in basename_variants(basename):
            queries.append(dict(basename=name, repo_ids=repos or None, fingerprint_value=None, limit=40))
            queries.append(dict(basename=name, repo_ids=None, fingerprint_value=fp or None, limit=40))
        queries.extend(
            [
                dict(basename=None, repo_ids=repos or None, fingerprint_value=fp or None, limit=40),
                dict(basename=None, repo_ids=None, fingerprint_value=fp or None, limit=40),
                dict(basename=None, repo_ids=repos or None, fingerprint_value=None, tokens=distinctive, limit=40),
                dict(basename=None, repo_ids=None, fingerprint_value=None, tokens=distinctive, limit=40),
            ]
        )
        for q in queries:
            if not q.get("basename") and not q.get("fingerprint_value") and not q.get("tokens"):
                continue
            for site in search_sites(conn, **q):
                key = (site["repo_id"], site["git_commit"], site["path"], site["line"])
                if key in seen:
                    continue
                seen.add(key)
                score, reasons = _score(record, site)
                if score < 20:
                    continue
                meta = snaps.get((site["repo_id"], site["git_commit"])) or {}
                candidates.append(
                    {
                        "repo_id": site["repo_id"],
                        "commit": site["git_commit"],
                        "ref": meta.get("ref"),
                        "indexed_at": meta.get("indexed_at"),
                        "path": site["path"],
                        "line": site["line"],
                        "func": site["func"],
                        "macro": site["macro"],
                        "level": site["level"],
                        "fmt": site["fmt"],
                        "source_line": site["source_line"],
                        "score": score,
                        "confidence": _confidence(score),
                        "reasons": reasons,
                        "line_drift": "line_drift" in reasons or "basename_variant" in reasons,
                    }
                )
        candidates.sort(key=lambda x: x["score"], reverse=True)
        decoded = decode_return_codes(record.get("msg_body") or record.get("msg"))
        embedded = None
        if record.get("file"):
            embedded = {
                "file": record.get("file"),
                "line": record.get("line"),
                "from_log": True,
                "repos": repos,
            }
        top = candidates[:limit]
        return {
            "parsed": {k: record.get(k) for k in ("level", "module", "file", "line", "msg", "parser", "error_codes")},
            "embedded": embedded,
            "signals": signals_for(record),
            "return_codes": decoded,
            "basis": analysis_basis(record, top, snaps),
            "locations": top,
        }
    finally:
        if own:
            conn.close()


def locate_text(text: str, source_path: str | None = None, limit: int = 5) -> list[dict[str, Any]]:
    conn = connect()
    try:
        return [locate_record(rec, conn=conn, limit=limit) for rec in parse_text(text, source_path)]
    finally:
        conn.close()


def locate_path(path: Path, limit: int = 5) -> list[dict[str, Any]]:
    conn = connect()
    try:
        return [locate_record(rec, conn=conn, limit=limit) for rec in parse_file(path)]
    finally:
        conn.close()


def locate_one(line: str) -> dict[str, Any]:
    return locate_record(parse_line(line))
