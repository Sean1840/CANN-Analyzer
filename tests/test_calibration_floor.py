"""Guards for the calibrated operating point.

The scored policy is a contract: lowering the acceptance floor or relaxing the fingerprint
overlap floor changes what an agent is told is "the code site". These tests fail if the
calibrated values drift without a measured reason (see eval/rubric.md, decision record).
"""

from __future__ import annotations

import json

import pytest

from cann_analyze.locate import DEFAULT_POLICY, load_policy, locate_one
from cann_analyze.paths import bundled_index_path, catalogs_dir, project_root

POLICY_FILE = catalogs_dir() / "locate_policy.json"
LABELED_CASES = catalogs_dir() / "eval" / "labeled_cases.json"


def _cases() -> list[dict]:
    data = json.loads(LABELED_CASES.read_text(encoding="utf-8"))
    return list(data.get("cases") or [])


def _negatives() -> list[dict]:
    return [case for case in _cases() if case.get("kind") == "negative"]


def _lines_of(case: dict) -> list[str]:
    if case.get("line"):
        return [case["line"]]
    log = case.get("log")
    if not log:
        return []
    path = project_root() / log
    if not path.is_file():
        return []
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_min_score_is_not_lowered_below_the_calibrated_floor():
    policy = load_policy()
    assert policy["min_score"] >= 25, (
        "min_score 25 is the calibrated operating point: at 20 a generic "
        "'malloc failed, size=4096' line was admitted by fingerprint_overlap alone"
    )
    assert DEFAULT_POLICY["min_score"] == policy["min_score"], "built-in fallback must match the shipped policy"


def test_fingerprint_overlap_floor_is_not_relaxed():
    assert load_policy()["weights"]["fingerprint_overlap_floor"] >= 0.6


def test_labeled_set_declares_both_polarities():
    cases = _cases()
    assert cases, "the calibration set must not be empty"
    kinds = {case.get("kind") for case in cases}
    assert {"line", "log", "negative"} <= kinds, f"calibration set is missing polarities: {sorted(kinds)}"


def test_labeled_negatives_do_not_resolve_under_the_shipped_policy():
    if not bundled_index_path().is_file():
        pytest.skip("bundled baseline index is not present")
    negatives = _negatives()
    assert negatives, "the calibration set must contain negative cases"

    offenders: list[str] = []
    checked = 0
    for case in negatives:
        for line in _lines_of(case):
            checked += 1
            result = locate_one(line)
            if result.get("locations"):
                top = result["locations"][0]
                offenders.append(f"{case['id']}: score={top['score']} {top['path']}")
    assert checked >= len(negatives), "every negative case must yield at least one line to score"
    assert not offenders, "negatives must not resolve under the shipped policy:\n" + "\n".join(offenders)


def test_generic_allocator_case_stays_below_the_floor():
    """The case that moved the floor from 20 to 25 must stay a miss."""
    if not bundled_index_path().is_file():
        pytest.skip("bundled baseline index is not present")
    malloc_cases = [case for case in _negatives() if "malloc" in json.dumps(case)]
    if not malloc_cases:
        pytest.skip("the documented malloc negative is not in the calibration set")
    for case in malloc_cases:
        for line in _lines_of(case):
            result = locate_one(line)
            assert not result.get("locations"), f"{case['id']} must stay below min_score"
            assert result.get("index_miss") is True


def test_policy_file_and_builtin_defaults_agree_on_every_scoring_key():
    policy = load_policy()
    assert policy["weights"] == DEFAULT_POLICY["weights"]
    assert policy["min_score"] == DEFAULT_POLICY["min_score"]
    assert policy["confidence"] == DEFAULT_POLICY["confidence"]
    assert policy["limits"] == DEFAULT_POLICY["limits"]
    assert policy["query_planner"] == DEFAULT_POLICY["query_planner"]
    assert policy["line_refresh_delta"] == DEFAULT_POLICY["line_refresh_delta"]
