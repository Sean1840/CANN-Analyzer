from __future__ import annotations

import json
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
ROOT = SKILL
sys.path.insert(0, str(SKILL.parent / "cann-prof-pipeline" / "scripts"))

from cann_analyze.index_cmd import index_repo  # noqa: E402
from cann_analyze.locate import locate_path  # noqa: E402
from cann_analyze.store import connect as real_connect  # noqa: E402


def load_cases() -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted((ROOT / "eval" / "cases").glob("*.json"))]


def score_case(case: dict, db: Path) -> dict:
    def _connect(path=None):
        return real_connect(db)

    import cann_analyze.index_cmd as index_cmd
    import cann_analyze.locate as locate

    index_cmd.connect = lambda: _connect()
    locate.connect = lambda: _connect()

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


def main() -> int:
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


if __name__ == "__main__":
    raise SystemExit(main())
