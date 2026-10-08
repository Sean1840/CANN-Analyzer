from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from cann_analyze.catalog import cann_error_codes, return_codes
from cann_analyze.fingerprint import fingerprint, tokens, token_overlap
from cann_analyze.parsers import parse_file, parse_line, parse_text
from cann_analyze.paths import catalogs_dir
from cann_analyze.stage_signals import candidate_repos, signals_for
from cann_analyze.store import connect, search_sites, snapshot_map

POLICY_SCHEMA = "cann-analyze.locate-policy.v1"
POLICY_FILENAME = "locate_policy.json"

# Built-in copy of catalogs/locate_policy.json. That file is the contract; this dict is
# the fallback so a missing or corrupt policy degrades to the documented behaviour
# instead of raising. tests/test_locate_policy.py fails if the two drift apart.
DEFAULT_POLICY: dict[str, Any] = {
    "schema": POLICY_SCHEMA,
    "notes": ["Built-in fallback for catalogs/locate_policy.json."],
    "weights": {
        "fingerprint_exact": 50,
        "fingerprint_overlap_multiplier": 30,
        "fingerprint_overlap_floor": 0.6,
        "basename": 40,
        "path_suffix": 20,
        "path_variant": 12,
        "line_exact": 20,
        "line_near": 10,
        "line_near_tolerance": 15,
        "level": 4,
        "error_code": 15,
        "module": 10,
    },
    "min_score": 25,
    "confidence": {
        "bands": [
            {"name": "high", "min_score": 80},
            {"name": "medium", "min_score": 50},
            {"name": "low", "min_score": 25},
        ],
        "fallback": "weak",
    },
    "line_refresh_delta": 20,
    "limits": {"query_fetch_limit": 40, "default_result_limit": 5},
    "query_planner": {"distinctive_min_length": 5, "distinctive_max_tokens": 6},
}


def _merge_policy(raw: Any, defaults: dict[str, Any]) -> dict[str, Any]:
    """Overlay untrusted JSON on defaults, keeping known keys and matching types only."""
    data = raw if isinstance(raw, dict) else {}
    out: dict[str, Any] = {}
    for key, default in defaults.items():
        value = data.get(key)
        if isinstance(default, dict):
            out[key] = _merge_policy(value, default)
        elif isinstance(default, bool):
            out[key] = value if isinstance(value, bool) else default
        elif isinstance(default, int):
            ok = isinstance(value, (int, float)) and not isinstance(value, bool)
            out[key] = int(value) if ok else default
        elif isinstance(default, float):
            ok = isinstance(value, (int, float)) and not isinstance(value, bool)
            out[key] = float(value) if ok else default
        elif isinstance(default, list) and default and all(isinstance(d, str) for d in default):
            kept = [v for v in value if isinstance(v, str)] if isinstance(value, list) else []
            out[key] = kept or list(default)
        elif isinstance(default, list):
            out[key] = list(default)
        else:
            out[key] = value if isinstance(value, str) and value else default
    return out


def _coerce_bands(value: Any, defaults: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep well-formed {name, min_score} bands, sorted high to low."""
    bands: list[dict[str, Any]] = []
    for item in value if isinstance(value, list) else []:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        floor = item.get("min_score")
        if isinstance(name, str) and name and isinstance(floor, (int, float)) and not isinstance(floor, bool):
            bands.append({"name": name, "min_score": int(floor)})
    if not bands:
        return [dict(band) for band in defaults]
    bands.sort(key=lambda band: band["min_score"], reverse=True)
    return bands


def load_policy(path: Path | str | None = None) -> dict[str, Any]:
    """Return the locate scoring policy, merged onto DEFAULT_POLICY. Never raises.

    A missing file, unreadable file, invalid JSON, non-object document, or wrong-typed
    field only loses that field: everything else keeps its documented default.
    """
    source = Path(path) if path is not None else catalogs_dir() / POLICY_FILENAME
    raw: Any = None
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except Exception:
        raw = None
    policy = _merge_policy(raw, DEFAULT_POLICY)
    confidence = raw.get("confidence") if isinstance(raw, dict) else None
    if not isinstance(confidence, dict):
        confidence = {}
    fallback = confidence.get("fallback")
    policy["confidence"] = {
        "bands": _coerce_bands(confidence.get("bands"), DEFAULT_POLICY["confidence"]["bands"]),
        "fallback": fallback if isinstance(fallback, str) and fallback else DEFAULT_POLICY["confidence"]["fallback"],
    }
    return policy


# Loaded once at import; functions read POLICY per call so tests can monkeypatch it.
POLICY: dict[str, Any] = load_policy()

# Compatibility mirror of the policy value. analysis_basis reads POLICY itself, so this
# module attribute only needs to exist for external callers.
LINE_REFRESH_DELTA = int(POLICY["line_refresh_delta"])


def _policy() -> dict[str, Any]:
    return POLICY if isinstance(POLICY, dict) else DEFAULT_POLICY


def _section(name: str) -> dict[str, Any]:
    value = _policy().get(name)
    if isinstance(value, dict):
        return value
    fallback = DEFAULT_POLICY[name]
    return fallback if isinstance(fallback, dict) else {}


def _weights() -> dict[str, Any]:
    return _section("weights")


def _limits() -> dict[str, Any]:
    return _section("limits")


def _planner() -> dict[str, Any]:
    return _section("query_planner")


def _min_score() -> int:
    try:
        return int(_policy().get("min_score", DEFAULT_POLICY["min_score"]))
    except (TypeError, ValueError):
        return int(DEFAULT_POLICY["min_score"])


def _line_refresh_delta() -> int:
    try:
        return int(_policy().get("line_refresh_delta", DEFAULT_POLICY["line_refresh_delta"]))
    except (TypeError, ValueError):
        return int(DEFAULT_POLICY["line_refresh_delta"])


def policy_hash(policy: dict[str, Any] | None = None) -> str:
    """sha256 of the effective policy so a measured baseline is reproducible.

    The informational `notes` list is excluded: prose edits must not invalidate a
    baseline, only changes to scoring values, bands, or limits should.
    """
    target = dict(POLICY if policy is None else policy)
    target.pop("notes", None)
    blob = json.dumps(target, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


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


_CANN_CODE = re.compile(r"\b([EWI])([A-Z0-9])(\d{4})\b")


def decode_return_codes(text: str | None) -> list[dict[str, str]]:
    if not text:
        return []
    catalog = return_codes()
    enums = catalog.get("enums") or {}
    fields = catalog.get("message_fields") or {}
    found: list[dict[str, str]] = []
    for match in _RET_FIELD.finditer(text):
        raw = match.group(1)
        for enum_name, table in enums.items():
            label = table.get(raw)
            if label:
                found.append({"field": "ret", "value": raw, "name": label, "enum": enum_name})
    cann = cann_error_codes()
    modules = cann.get("module") or {}
    levels = cann.get("level") or {}
    titles = cann.get("codes") or {}
    seen = {x["value"] for x in found}
    for match in _CANN_CODE.finditer(text):
        code = match.group(0)
        if code in seen:
            continue
        seen.add(code)
        rec = titles.get(code) or {}
        mod = modules.get(match.group(2)) or {}
        found.append(
            {
                "field": "cann_code",
                "value": code,
                "name": str(rec.get("module") or mod.get("name") or "unknown"),
                "title": str(rec.get("title") or ""),
                "repo": str(rec.get("repo") if rec.get("repo") is not None else mod.get("repo") or ""),
                "level": str(rec.get("level") or levels.get(match.group(1)) or match.group(1)),
                "internal": bool(rec.get("internal")),
            }
        )
    return found


def _score(record: dict[str, Any], site: dict[str, Any]) -> tuple[int, list[str]]:
    """Score one candidate site. Every point value comes from the loaded policy."""
    weights = _weights()
    reasons: list[str] = []
    score = 0
    rec_fp = record.get("fingerprint") or fingerprint(record.get("msg") or "")
    site_fp = site.get("fingerprint") or ""
    rec_base = _basename(record.get("file"))
    site_base = site.get("basename")
    rec_line = record.get("line")
    site_line = site.get("line")

    if rec_fp and site_fp and rec_fp == site_fp:
        score += int(weights["fingerprint_exact"])
        reasons.append("fingerprint_exact")
    else:
        overlap = token_overlap(rec_fp, site_fp)
        if overlap >= float(weights["fingerprint_overlap_floor"]):
            score += int(int(weights["fingerprint_overlap_multiplier"]) * overlap)
            reasons.append(f"fingerprint_overlap:{overlap:.2f}")

    rec_bases = set(basename_variants(rec_base))
    if rec_base and site_base and site_base in rec_bases:
        score += int(weights["basename"])
        reasons.append("basename" if site_base == rec_base else "basename_variant")
        rec_file = (record.get("file") or "").replace("\\", "/")
        if rec_file and site.get("path", "").endswith(rec_file):
            score += int(weights["path_suffix"])
            reasons.append("path_suffix")
        elif any(site.get("path", "").endswith(v) for v in rec_bases):
            score += int(weights["path_variant"])
            reasons.append("path_variant")

    if rec_line and site_line:
        if rec_line == site_line:
            score += int(weights["line_exact"])
            reasons.append("line_exact")
        elif abs(rec_line - site_line) <= int(weights["line_near_tolerance"]):
            score += int(weights["line_near"])
            reasons.append("line_near")
        elif rec_base == site_base:
            reasons.append("line_drift")

    rec_level = record.get("level")
    if rec_level and rec_level == site.get("level"):
        score += int(weights["level"])
        reasons.append("level")

    rec_codes = set(record.get("error_codes") or [])
    try:
        site_codes = set(json.loads(site.get("error_codes") or "[]"))
    except Exception:
        site_codes = set()
    if rec_codes and rec_codes & site_codes:
        score += int(weights["error_code"])
        reasons.append("error_code")

    module = (record.get("module") or "").upper()
    hint = (site.get("module_hint") or "").upper()
    if module and hint and module == hint:
        score += int(weights["module"])
        reasons.append("module")

    return score, reasons


def _confidence(score: int) -> str:
    """Map a kept score to a confidence band using the policy band table."""
    spec = _policy().get("confidence")
    if not isinstance(spec, dict):
        spec = DEFAULT_POLICY["confidence"]
    for band in spec.get("bands") or []:
        try:
            floor = int(band["min_score"])
        except (KeyError, TypeError, ValueError):
            continue
        if score >= floor:
            return str(band["name"])
    return str(spec.get("fallback") or DEFAULT_POLICY["confidence"]["fallback"])


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
        if rec_line and loc_line and abs(int(rec_line) - int(loc_line)) > _line_refresh_delta():
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
            "分析未命中内置基线索引（catalogs/baseline/sites.sqlite），仅依据日志内嵌 file:line。"
            "先对缺失仓执行 index --repo <id> --source <已有clone> 更新本地 overlay；"
            "不要为了查行号去 clone。只有需要读实现分析原因/方案时再拉代码。"
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


def locate_record(
    record: dict[str, Any],
    conn=None,
    limit: int | None = None,
    min_score: int | None = None,
) -> dict[str, Any]:
    """Locate index sites for one parsed log record.

    limit and min_score default to the loaded policy (limits.default_result_limit and
    min_score). min_score is the explicit negative-case control: raise it to demand
    stronger evidence, or set it above the highest reachable score to assert that this
    log must not resolve to any site at all.
    """
    own = conn is None
    conn = conn or connect()
    try:
        limits = _limits()
        planner = _planner()
        fetch_limit = int(limits.get("query_fetch_limit", DEFAULT_POLICY["limits"]["query_fetch_limit"]))
        result_limit = int(limits.get("default_result_limit", DEFAULT_POLICY["limits"]["default_result_limit"])) if limit is None else int(limit)
        threshold = _min_score() if min_score is None else int(min_score)
        min_token_length = int(planner.get("distinctive_min_length", 5))
        max_tokens = int(planner.get("distinctive_max_tokens", 6))
        snaps = snapshot_map(conn)
        repos = candidate_repos(record)
        basename = _basename(record.get("file"))
        fp = record.get("fingerprint") or fingerprint(record.get("msg_body") or record.get("msg") or "")
        distinctive = [t for t in tokens(fp) if len(t) >= min_token_length][:max_tokens]
        candidates: list[dict[str, Any]] = []
        seen: set[tuple] = set()
        queries: list[dict[str, Any]] = []
        for name in basename_variants(basename):
            queries.append(dict(basename=name, repo_ids=repos or None, fingerprint_value=None, limit=fetch_limit))
            queries.append(dict(basename=name, repo_ids=None, fingerprint_value=fp or None, limit=fetch_limit))
        queries.append(dict(basename=None, repo_ids=repos or None, fingerprint_value=fp or None, limit=fetch_limit))
        queries.append(dict(basename=None, repo_ids=None, fingerprint_value=fp or None, limit=fetch_limit))
        if distinctive:
            # No distinctive token means no token query at all: an empty token list
            # would only widen the scan to every indexed site.
            queries.append(dict(basename=None, repo_ids=repos or None, fingerprint_value=None, tokens=distinctive, limit=fetch_limit))
            queries.append(dict(basename=None, repo_ids=None, fingerprint_value=None, tokens=distinctive, limit=fetch_limit))
        for q in queries:
            if not q.get("basename") and not q.get("fingerprint_value") and not q.get("tokens"):
                continue
            for site in search_sites(conn, **q):
                key = (site["repo_id"], site["git_commit"], site["path"], site["line"])
                if key in seen:
                    continue
                seen.add(key)
                score, reasons = _score(record, site)
                if score < threshold:
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
        decoded = decode_return_codes(
            " ".join(str(record.get(k) or "") for k in ("raw", "msg", "msg_body"))
        )
        embedded = None
        if record.get("file"):
            embedded = {
                "file": record.get("file"),
                "line": record.get("line"),
                "from_log": True,
                "repos": repos,
            }
        top = candidates[:result_limit]
        parsed_keys = ("level", "module", "file", "line", "tid", "msg", "parser", "error_codes")
        return {
            "parsed": {k: record.get(k) for k in parsed_keys},
            "embedded": embedded,
            "signals": signals_for(record),
            "return_codes": decoded,
            "index_miss": not bool(top),
            "basis": analysis_basis(record, top, snaps),
            "locations": top,
        }
    finally:
        if own:
            conn.close()


def locate_text(text: str, source_path: str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
    conn = connect()
    try:
        return [locate_record(rec, conn=conn, limit=limit) for rec in parse_text(text, source_path)]
    finally:
        conn.close()


def locate_path(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    conn = connect()
    try:
        return [locate_record(rec, conn=conn, limit=limit) for rec in parse_file(path)]
    finally:
        conn.close()


def locate_one(line: str) -> dict[str, Any]:
    return locate_record(parse_line(line))
