"""Locator evaluation.

Default mode scores eval/cases/*.json on a throw-away mini_repo index, exactly as
before. Calibration mode (`--labeled`) scores catalogs/eval/labeled_cases.json against
the shipped catalogs/baseline/sites.sqlite index and prints a reproducible operating
point: hit@1 / hit@3 / miss / false-positive rates, a per-confidence-band breakdown, a
monotonicity check, and the schema plus hash of the policy that was actually used.

Run from the repo root:

    PYTHONPATH=tools python eval/run_eval.py
    PYTHONPATH=tools python eval/run_eval.py --labeled
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from cann_analyze.index_cmd import index_repo  # noqa: E402
from cann_analyze.locate import load_policy, locate_path, locate_record, policy_hash  # noqa: E402
from cann_analyze.parsers import parse_file, parse_line  # noqa: E402
from cann_analyze.paths import bundled_index_path, catalogs_dir  # noqa: E402
from cann_analyze.store import connect as real_connect, list_snapshots  # noqa: E402

LABELED_PATH = ROOT / "catalogs" / "eval" / "labeled_cases.json"
POLICY_PATH = ROOT / "catalogs" / "locate_policy.json"
BAND_ORDER = ("high", "medium", "low", "weak", "none")
CALIBRATION_TOP_K = 3


# --------------------------------------------------------------------------------------
# shared helpers
# --------------------------------------------------------------------------------------


def _isolated_connect(db: Path):
    """Build a connect() replacement pinned to db.

    store.connect(path, *, write=False) is the real signature and index_cmd calls
    connect(write=True): accept and forward kwargs, but always route to db so a run
    never touches the shipped baseline or the user overlay.
    """

    def _connect(path=None, **kwargs):
        return real_connect(db, **kwargs)

    return _connect


def _patch_connect(db: Path) -> None:
    import cann_analyze.index_cmd as index_cmd
    import cann_analyze.locate as locate

    _connect = _isolated_connect(db)
    index_cmd.connect = _connect
    locate.connect = _connect


# --------------------------------------------------------------------------------------
# default mode: committed eval cases on an isolated mini_repo index
# --------------------------------------------------------------------------------------


def load_cases() -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted((ROOT / "eval" / "cases").glob("*.json"))]


def score_case(case: dict, db: Path) -> dict:
    _patch_connect(db)

    index_repo(
        case["index_repo"],
        source=ROOT / case["index_source"],
        commit="eval",
    )
    log_path = ROOT / case["log"]
    results = locate_path(log_path, limit=3)
    expect = case["expect"]
    want_level = (expect.get("parsed") or {}).get("level")
    suffix = expect.get("path_suffix")

    def _paths(item: dict) -> list[str]:
        return [loc.get("path") or "" for loc in item.get("locations") or []]

    ranked = [r for r in results if (not want_level) or r.get("parsed", {}).get("level") == want_level]
    ranked = ranked or results
    first = next(
        (r for r in ranked if suffix and any(p.endswith(suffix) for p in _paths(r))),
        ranked[0] if ranked else {},
    )
    parsed = first.get("parsed") or {}
    parse_ok = True
    for key, value in (expect.get("parsed") or {}).items():
        if parsed.get(key) != value:
            parse_ok = False
    locs = first.get("locations") or []
    paths = _paths(first)
    embedded = ((first.get("embedded") or {}).get("file") or "")
    hit1 = bool(paths and suffix and paths[0].endswith(suffix))
    hit3 = bool(suffix and any(p.endswith(suffix) for p in paths)) or (suffix and embedded.endswith(suffix))
    if not hit1 and suffix and embedded.endswith(suffix):
        hit1 = True
    if not hit3:
        hit3 = bool(
            suffix
            and any(
                any(p.endswith(suffix) for p in _paths(r))
                or str((r.get("embedded") or {}).get("file") or "").endswith(suffix)
                for r in results
            )
        )
    if not hit1:
        hit1 = hit3
    line_ok = True
    if expect.get("line") is not None and locs:
        tol = int(expect.get("line_tolerance") or 15)
        line_ok = abs(int(locs[0]["line"]) - int(expect["line"])) <= tol
    signals = first.get("signals") or []
    signal_ok = all(s in signals for s in expect.get("signals") or [])
    no_verdict = "verdict" not in first and "root_cause" not in first and "diagnosis" not in first
    metrics = {
        "parse_ok": parse_ok,
        "locate_hit@1": hit1,
        "locate_hit@3": hit3,
        "line_tolerance": line_ok,
        "signal_hit": signal_ok,
        "no_verdict": no_verdict,
    }
    passed = all(metrics.values())
    return {"id": case["id"], "pass": passed, "metrics": metrics, "top": locs[:1], "signals": signals}


def run_default() -> int:
    db = ROOT / "data" / "indexes" / "eval.sqlite"
    db.parent.mkdir(parents=True, exist_ok=True)
    if db.exists():
        db.unlink()
    rows = [score_case(case, db) for case in load_cases()]
    summary = {
        "passed": sum(1 for r in rows if r["pass"]),
        "total": len(rows),
        "cases": rows,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["passed"] == summary["total"] else 1


# --------------------------------------------------------------------------------------
# calibration mode: labeled positives and negatives on the shipped baseline index
# --------------------------------------------------------------------------------------


def load_labeled() -> dict:
    return json.loads(LABELED_PATH.read_text(encoding="utf-8"))


def _case_records(case: dict) -> list[dict]:
    line = case.get("line")
    if line is not None:
        return [parse_line(line)]
    log = case.get("log")
    if not log:
        raise ValueError(f"case {case.get('id')!r} has neither line nor log")
    path = ROOT / str(log)
    if not path.is_file():
        raise FileNotFoundError(f"case {case.get('id')!r} references missing log {path}")
    return parse_file(path)


def _location_matches(loc: dict[str, Any], expect: dict[str, Any]) -> bool:
    repo = expect.get("repo_id")
    if repo and loc.get("repo_id") != repo:
        return False
    suffix = expect.get("path_suffix")
    if suffix and not str(loc.get("path") or "").endswith(suffix):
        return False
    want_line = expect.get("line")
    if want_line is not None:
        try:
            tolerance = int(expect.get("line_tolerance", 15))
            if abs(int(loc.get("line") or 0) - int(want_line)) > tolerance:
                return False
        except (TypeError, ValueError):
            return False
    return True


def _brief(loc: dict[str, Any]) -> dict[str, Any]:
    return {
        "repo_id": loc.get("repo_id"),
        "path": loc.get("path"),
        "line": loc.get("line"),
        "score": int(loc.get("score") or 0),
        "confidence": loc.get("confidence"),
        "reasons": list(loc.get("reasons") or []),
    }


def _score_positive(case: dict, conn, floor: int) -> dict[str, Any]:
    """Best rank over every record of the case, plus rank-vs-score ordering checks."""
    expect = case.get("expect") or {}
    match: dict[str, Any] | None = None
    ordering_violations: list[str] = []
    for record in _case_records(case):
        result = locate_record(record, conn=conn, limit=CALIBRATION_TOP_K, min_score=floor)
        locations = result.get("locations") or []
        scores = [int(loc.get("score") or 0) for loc in locations]
        if scores != sorted(scores, reverse=True):
            ordering_violations.append(f"{case['id']}: returned scores not descending: {scores}")
        for rank, loc in enumerate(locations, start=1):
            if not _location_matches(loc, expect):
                continue
            if any(s < int(loc.get("score") or 0) for s in scores[: rank - 1]):
                ordering_violations.append(f"{case['id']}: rank {rank} scored above a higher-ranked location")
            candidate = dict(_brief(loc), rank=rank)
            if match is None or candidate["rank"] < match["rank"]:
                match = candidate
    return {"id": case["id"], "kind": case.get("kind", "line"), "match": match, "ordering_violations": ordering_violations}


def _score_negative(case: dict, conn, floor: int) -> dict[str, Any]:
    """Any returned location is a false positive; also probe the floor margin."""
    hits: list[dict[str, Any]] = []
    best: dict[str, Any] | None = None
    for record in _case_records(case):
        result = locate_record(record, conn=conn, limit=CALIBRATION_TOP_K, min_score=floor)
        for loc in result.get("locations") or []:
            hits.append(_brief(loc))
        probe = locate_record(record, conn=conn, limit=1, min_score=0)
        top = (probe.get("locations") or [None])[0]
        if top is not None:
            brief = _brief(top)
            if best is None or brief["score"] > best["score"]:
                best = brief
    return {
        "id": case["id"],
        "kind": case.get("kind", "negative"),
        "false_positive": bool(hits),
        "hits": hits,
        "best_candidate_below_floor": best,
        "floor_margin": (floor - best["score"]) if best else None,
        "floor": floor,
    }


def _policy_source() -> str:
    if not POLICY_PATH.is_file():
        return "<built-in defaults>"
    try:
        return str(POLICY_PATH.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(POLICY_PATH)


def calibrate(floor_override: int | None = None) -> dict[str, Any]:
    spec = load_labeled()
    policy = load_policy()
    floor = int(policy["min_score"]) if floor_override is None else int(floor_override)
    db = bundled_index_path()
    if not db.is_file():
        raise FileNotFoundError(f"shipped baseline index missing: {db}")
    _patch_connect(db)
    conn = real_connect(db)
    try:
        snaps = list_snapshots(conn)
        positives = [c for c in spec["cases"] if c.get("kind") != "negative"]
        negatives = [c for c in spec["cases"] if c.get("kind") == "negative"]
        positive_rows = [_score_positive(case, conn, floor) for case in positives]
        negative_rows = [_score_negative(case, conn, floor) for case in negatives]
    finally:
        conn.close()

    bands: dict[str, dict[str, int]] = {
        name: {"hit@1": 0, "hit@3": 0, "miss": 0, "cases": 0, "false_positive": 0} for name in BAND_ORDER
    }
    hit1_scores: list[dict[str, Any]] = []
    ranked_only_scores: list[dict[str, Any]] = []
    for row in positive_rows:
        match = row["match"]
        band = match["confidence"] if match and match["confidence"] in bands else "none"
        bands[band]["cases"] += 1
        if match is None:
            bands[band]["miss"] += 1
            continue
        if match["rank"] == 1:
            bands[band]["hit@1"] += 1
            hit1_scores.append({"id": row["id"], "score": match["score"]})
        else:
            ranked_only_scores.append({"id": row["id"], "rank": match["rank"], "score": match["score"]})
        if match["rank"] <= CALIBRATION_TOP_K:
            bands[band]["hit@3"] += 1
    for row in negative_rows:
        for hit in row["hits"]:
            band = hit["confidence"] if hit["confidence"] in bands else "none"
            bands[band]["false_positive"] += 1

    ordering_violations = [v for row in positive_rows for v in row["ordering_violations"]]
    worst_hit1 = min((item["score"] for item in hit1_scores), default=None)
    best_ranked_only = max((item["score"] for item in ranked_only_scores), default=None)
    if worst_hit1 is None or best_ranked_only is None:
        cross_case_ok: bool | None = None
        cross_case_note = "not exercised: every positive matched at rank 1 or none did"
    else:
        cross_case_ok = worst_hit1 >= best_ranked_only
        cross_case_note = "worst hit@1 score must be >= best score of a case matched only at rank 2..3"

    n_pos = len(positive_rows)
    n_neg = len(negative_rows)
    hit1 = sum(1 for row in positive_rows if row["match"] and row["match"]["rank"] == 1)
    hit3 = sum(1 for row in positive_rows if row["match"] and row["match"]["rank"] <= CALIBRATION_TOP_K)
    misses = n_pos - hit3
    false_positives = [row for row in negative_rows if row["false_positive"]]

    def rate(part: int, total: int) -> float | None:
        return round(part / total, 4) if total else None

    return {
        "generated_from": str(LABELED_PATH.relative_to(ROOT)).replace("\\", "/"),
        "command": "PYTHONPATH=tools python eval/run_eval.py --labeled",
        "policy": {
            "source": _policy_source(),
            "schema": policy["schema"],
            "sha256": policy_hash(policy),
            "min_score": int(policy["min_score"]),
            "bands": policy["confidence"],
            "floor_used": floor,
            "floor_override": floor_override,
        },
        "index": {
            "db": str(db.relative_to(ROOT)).replace("\\", "/"),
            "sha256_16": hashlib.sha256(db.read_bytes()).hexdigest()[:16],
            "snapshots": len(snaps),
            "sites": sum(int(s.get("site_count") or 0) for s in snaps),
            "repos": sorted({str(s.get("repo_id")) for s in snaps}),
        },
        "positives": {
            "total": n_pos,
            "hit@1": hit1,
            "hit@3": hit3,
            "miss": misses,
            "hit@1_rate": rate(hit1, n_pos),
            "hit@3_rate": rate(hit3, n_pos),
            "miss_rate": rate(misses, n_pos),
        },
        "negatives": {
            "total": n_neg,
            "false_positives": len(false_positives),
            "false_positive_rate": rate(len(false_positives), n_neg),
            "floor": floor,
            "details": negative_rows,
        },
        "by_confidence": bands,
        "monotonicity": {
            "rank_order_matches_score": not ordering_violations,
            "ordering_violations": ordering_violations,
            "cross_case_ok": cross_case_ok,
            "cross_case_note": cross_case_note,
            "worst_hit@1_score": worst_hit1,
            "best_rank_2_3_score": best_ranked_only,
        },
        "cases": {"positives": positive_rows, "negatives": negative_rows},
    }


def _print_calibration(summary: dict[str, Any]) -> None:
    policy = summary["policy"]
    index = summary["index"]
    pos = summary["positives"]
    neg = summary["negatives"]
    print("labeled calibration:", summary["generated_from"])
    print(f"command   : {summary['command']}")
    print(f"policy    : {policy['source']}")
    print(f"            schema={policy['schema']} sha256={policy['sha256']} min_score={policy['min_score']} "
          f"floor_used={policy['floor_used']}")
    print(f"index     : {index['db']} sha256_16={index['sha256_16']} snapshots={index['snapshots']} sites={index['sites']}")
    print(f"positives : n={pos['total']} hit@1={pos['hit@1']} ({pos['hit@1_rate']}) hit@3={pos['hit@3']} "
          f"({pos['hit@3_rate']}) miss={pos['miss']} ({pos['miss_rate']})")
    print("by confidence band (band of the matched location for positives, band of the hit for negatives;")
    print("misses are counted under none):")
    print(f"  {'band':8s} {'cases':>5s} {'hit@1':>6s} {'hit@3':>6s} {'miss':>5s} {'fp':>4s}")
    for band in BAND_ORDER:
        row = summary["by_confidence"][band]
        if not row["cases"] and not row["false_positive"] and band != "none":
            continue
        print(f"  {band:8s} {row['cases']:5d} {row['hit@1']:6d} {row['hit@3']:6d} {row['miss']:5d} {row['false_positive']:4d}")
    print(f"negatives : n={neg['total']} false-positives={neg['false_positives']} ({neg['false_positive_rate']}) floor={neg['floor']}")
    for row in neg["details"]:
        if row["false_positive"]:
            for hit in row["hits"]:
                print(f"  FALSE POSITIVE {row['id']}: score={hit['score']} confidence={hit['confidence']} "
                      f"{hit['path']}:{hit['line']} reasons={','.join(hit['reasons'])}")
        else:
            best = row["best_candidate_below_floor"]
            detail = "no candidate retrieved" if not best else f"best below floor={best['score']} margin={row['floor_margin']}"
            print(f"  ok              {row['id']}: {detail}")
    mono = summary["monotonicity"]
    print(f"monotonicity: rank_order_matches_score={mono['rank_order_matches_score']} "
          f"cross_case_ok={mono['cross_case_ok']} worst_hit@1={mono['worst_hit@1_score']} "
          f"best_rank_2_3={mono['best_rank_2_3_score']}")
    print("  note:", mono["cross_case_note"])
    for case in summary["cases"]["positives"]:
        match = case["match"]
        shown = "MISS" if not match else f"rank={match['rank']} score={match['score']} {match['confidence']} {match['path']}:{match['line']}"
        print(f"  positive {case['id']:26s} {shown}")
    print("result:", "OK" if not neg["false_positives"] else "NEGATIVE CASE PASSED THE SCORE FLOOR (see false positive above)")


def run_labeled(as_json: bool = False, floor_override: int | None = None, strict: bool = False) -> int:
    """Print the calibration report; without --strict a measured miss is not a failure."""
    summary = calibrate(floor_override=floor_override)
    if as_json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        _print_calibration(summary)
    if not strict:
        return 0
    failed = bool(summary["negatives"]["false_positives"]) or bool(summary["positives"]["miss"])
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score the CANN-Analyzer locator.")
    parser.add_argument("--labeled", action="store_true", help="score catalogs/eval/labeled_cases.json on the shipped baseline index")
    parser.add_argument("--json", action="store_true", help="with --labeled, print the full report as JSON")
    parser.add_argument("--floor", type=int, default=None,
                        help="with --labeled, override the policy min_score to measure a what-if operating point")
    parser.add_argument("--strict", action="store_true",
                        help="with --labeled, exit 1 when a negative case hits or a positive case misses")
    args = parser.parse_args(argv)
    if args.labeled:
        return run_labeled(as_json=args.json, floor_override=args.floor, strict=args.strict)
    return run_default()


if __name__ == "__main__":
    raise SystemExit(main())
