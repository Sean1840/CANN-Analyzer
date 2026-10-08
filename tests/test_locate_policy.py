"""Contract tests for the externalised locate scoring policy.

catalogs/locate_policy.json is the scoring contract; tools/cann_analyze/locate.py ships an
identical built-in fallback. These tests pin the loader (never raises, defaults on a
missing/corrupt file), the policy-driven score, the documented band boundaries, ranking
determinism, and the negative-case behaviour (index_miss with no locations).
"""

from __future__ import annotations

import copy
import json

import pytest

from cann_analyze import locate
from cann_analyze.index_cmd import index_repo
from cann_analyze.locate import (
    DEFAULT_POLICY,
    LINE_REFRESH_DELTA,
    _confidence,
    _score,
    load_policy,
    locate_one,
    locate_record,
    policy_hash,
)
from cann_analyze.parsers import parse_line
from cann_analyze.paths import project_root

MINI = project_root() / "fixtures" / "mini_repo"
POLICY_FILE = project_root() / "catalogs" / "locate_policy.json"

CONTEXT_LINE = (
    "[ERROR] ASCENDCL(123,python):2026-09-02-18:11:41.121.000 "
    "[src/acl/aclrt_impl/context.cpp:244]create context failed, flags=1"
)
UNRELATED_LINE = "Quarterly newsletter: the harbourside pavilion luncheon has been postponed until further notice."
FABRICATED_LINE = (
    "[ERROR] MOCK(4242,python):2026-01-01-00:00:00.000.000 "
    "[src/zzz/quantum_flux_widget.cc:77]Quantum flux inversion aborted; widget telemetry unavailable."
)


def _deep_copy_policy() -> dict:
    return copy.deepcopy(DEFAULT_POLICY)


def _record(**overrides) -> dict:
    record = {
        "fingerprint": "",
        "file": None,
        "line": None,
        "level": None,
        "module": None,
        "error_codes": [],
        "msg": "",
    }
    record.update(overrides)
    return record


def _site(**overrides) -> dict:
    site = {
        "fingerprint": "",
        "basename": None,
        "path": "",
        "line": None,
        "level": None,
        "module_hint": None,
        "error_codes": "[]",
    }
    site.update(overrides)
    return site


# --------------------------------------------------------------------------------------
# loading and defaults
# --------------------------------------------------------------------------------------


def test_policy_file_loads_and_documents_the_contract():
    assert POLICY_FILE.is_file(), "catalogs/locate_policy.json is the scoring contract"
    policy = load_policy()
    assert policy["schema"] == "cann-analyze.locate-policy.v1"
    for key in ("weights", "min_score", "confidence", "line_refresh_delta", "limits", "query_planner"):
        assert key in policy, key
    for key in (
        "fingerprint_exact",
        "fingerprint_overlap_multiplier",
        "fingerprint_overlap_floor",
        "basename",
        "path_suffix",
        "path_variant",
        "line_exact",
        "line_near",
        "line_near_tolerance",
        "level",
        "error_code",
        "module",
    ):
        assert key in policy["weights"], key
    assert [band["name"] for band in policy["confidence"]["bands"]] == ["high", "medium", "low"]
    assert policy["confidence"]["fallback"] == "weak"
    assert {"query_fetch_limit", "default_result_limit"} <= set(policy["limits"])
    assert {"distinctive_min_length", "distinctive_max_tokens"} <= set(policy["query_planner"])
    assert isinstance(policy["notes"], list) and policy["notes"]


def test_shipped_policy_matches_builtin_default_scoring_values():
    """The file may only differ from the built-in fallback in its prose notes."""
    from_file = load_policy()
    baseline = _deep_copy_policy()
    assert from_file["notes"] != baseline["notes"] or True  # notes are free-form
    from_file.pop("notes")
    baseline.pop("notes")
    assert from_file == baseline


def test_missing_policy_file_falls_back_to_defaults(tmp_path):
    assert load_policy(tmp_path / "does_not_exist.json") == DEFAULT_POLICY


@pytest.mark.parametrize(
    "payload",
    [
        "{ not json at all",
        "[]",
        '"a string"',
        "",
    ],
)
def test_corrupt_policy_file_falls_back_to_defaults(tmp_path, payload):
    path = tmp_path / "locate_policy.json"
    path.write_text(payload, encoding="utf-8")
    policy = load_policy(path)
    assert policy["weights"] == DEFAULT_POLICY["weights"]
    assert policy["min_score"] == DEFAULT_POLICY["min_score"]
    assert policy["confidence"] == DEFAULT_POLICY["confidence"]
    assert policy["limits"] == DEFAULT_POLICY["limits"]
    assert policy["query_planner"] == DEFAULT_POLICY["query_planner"]


def test_partial_and_wrong_typed_policy_keeps_defaults_per_field(tmp_path):
    path = tmp_path / "locate_policy.json"
    path.write_text(
        json.dumps(
            {
                "schema": "cann-analyze.locate-policy.v1",
                "weights": {"fingerprint_exact": "fifty", "basename": 4},
                "min_score": "twenty",
                "line_refresh_delta": None,
                "confidence": {"bands": [{"name": "high"}], "fallback": 7},
                "limits": {"query_fetch_limit": "many"},
            }
        ),
        encoding="utf-8",
    )
    policy = load_policy(path)
    assert policy["weights"]["fingerprint_exact"] == DEFAULT_POLICY["weights"]["fingerprint_exact"]
    assert policy["weights"]["basename"] == 4
    assert policy["min_score"] == DEFAULT_POLICY["min_score"]
    assert policy["line_refresh_delta"] == DEFAULT_POLICY["line_refresh_delta"]
    assert policy["confidence"]["bands"] == DEFAULT_POLICY["confidence"]["bands"]
    assert policy["confidence"]["fallback"] == DEFAULT_POLICY["confidence"]["fallback"]
    assert policy["limits"]["query_fetch_limit"] == DEFAULT_POLICY["limits"]["query_fetch_limit"]


def test_policy_loader_never_raises(tmp_path):
    directory = tmp_path / "a_directory"
    directory.mkdir()
    assert load_policy(directory) == DEFAULT_POLICY
    binary = tmp_path / "binary.json"
    binary.write_bytes(b"\xff\xfe\x00\x01")
    assert load_policy(binary) == DEFAULT_POLICY


def test_line_refresh_delta_attribute_is_policy_backed():
    assert LINE_REFRESH_DELTA == load_policy()["line_refresh_delta"]
    assert isinstance(LINE_REFRESH_DELTA, int)


def test_policy_hash_is_stable_and_tracks_scoring_changes():
    assert policy_hash() == policy_hash(load_policy())
    mutated = _deep_copy_policy()
    mutated["weights"]["basename"] += 1
    assert policy_hash(mutated) != policy_hash()
    notes_only = _deep_copy_policy()
    notes_only["notes"] = ["different prose"]
    assert policy_hash(notes_only) == policy_hash()


# --------------------------------------------------------------------------------------
# scoring uses the documented weights
# --------------------------------------------------------------------------------------


def test_score_matches_policy_weights_for_each_signal():
    weights = load_policy()["weights"]
    exact = _score(_record(fingerprint="alpha beta gamma"), _site(fingerprint="alpha beta gamma"))[0]
    assert exact == weights["fingerprint_exact"]

    # 3 shared of 5 union tokens = 0.6, exactly the overlap floor.
    overlap = _score(_record(fingerprint="alpha beta gamma"), _site(fingerprint="alpha beta gamma delta epsilon"))[0]
    assert overlap == int(weights["fingerprint_overlap_multiplier"] * 0.6)

    no_overlap = _score(_record(fingerprint="alpha beta gamma"), _site(fingerprint="delta epsilon zeta"))[0]
    assert no_overlap == 0

    basename_only = _score(_record(file="x.cpp"), _site(basename="x.cpp", path="src/deep/x.cpp.in"))[0]
    assert basename_only == weights["basename"]

    basename_and_suffix = _score(_record(file="src/deep/x.cpp"), _site(basename="x.cpp", path="src/deep/x.cpp"))[0]
    assert basename_and_suffix == weights["basename"] + weights["path_suffix"]

    line_exact = _score(_record(line=100), _site(line=100))[0]
    assert line_exact == weights["line_exact"]

    line_near = _score(_record(line=100), _site(line=100 + weights["line_near_tolerance"]))[0]
    assert line_near == weights["line_near"]

    line_far = _score(_record(line=100), _site(line=100 + weights["line_near_tolerance"] + 1))[0]
    assert line_far == 0


def test_score_ordering_respects_documented_weights():
    weights = load_policy()["weights"]
    strong = _score(_record(fingerprint="alpha beta gamma"), _site(fingerprint="alpha beta gamma"))[0]
    weak = _score(_record(fingerprint="alpha beta gamma"), _site(fingerprint="alpha beta gamma delta epsilon"))[0]
    assert strong > weak

    base = _score(_record(file="src/deep/x.cpp"), _site(basename="x.cpp", path="src/deep/x.cpp"))[0]
    no_path = _score(_record(file="x.cpp"), _site(basename="x.cpp", path="src/deep/x.cpp.in"))[0]
    assert base == no_path + weights["path_suffix"]
    assert no_path == weights["basename"]
    assert weights["fingerprint_exact"] > weights["basename"] > weights["line_exact"] > weights["line_near"]
    assert weights["error_code"] > weights["module"] > weights["level"]


def test_score_reads_weights_from_the_loaded_policy(monkeypatch):
    record = _record(fingerprint="alpha beta gamma")
    site = _site(fingerprint="alpha beta gamma")
    baseline = _score(record, site)[0]

    boosted = _deep_copy_policy()
    boosted["weights"]["fingerprint_exact"] = baseline + 7
    monkeypatch.setattr(locate, "POLICY", boosted)
    assert _score(record, site)[0] == baseline + 7

    generic = _record(fingerprint="alpha beta gamma", file="src/deep/x.cpp")
    generic_site = _site(basename="x.cpp", path="src/deep/x.cpp")
    before = _score(generic, generic_site)[0]
    boosted = _deep_copy_policy()
    boosted["weights"]["basename"] = 400
    monkeypatch.setattr(locate, "POLICY", boosted)
    assert _score(generic, generic_site)[0] == before + 400 - DEFAULT_POLICY["weights"]["basename"]


def test_overlap_floor_is_policy_backed(monkeypatch):
    record = _record(fingerprint="alpha beta gamma")
    site = _site(fingerprint="alpha beta gamma delta epsilon")
    assert _score(record, site)[0] > 0

    raised = _deep_copy_policy()
    raised["weights"]["fingerprint_overlap_floor"] = 0.99
    monkeypatch.setattr(locate, "POLICY", raised)
    assert _score(record, site)[0] == 0


# --------------------------------------------------------------------------------------
# confidence bands
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (0, "weak"),
        (19, "weak"),
        (20, "weak"),
        (24, "weak"),
        (25, "low"),
        (49, "low"),
        (50, "medium"),
        (79, "medium"),
        (80, "high"),
        (10_000, "high"),
    ],
)
def test_confidence_band_boundaries(score, expected):
    assert _confidence(score) == expected


def test_confidence_bands_are_sorted_and_policy_backed(monkeypatch):
    policy = load_policy()
    floors = [band["min_score"] for band in policy["confidence"]["bands"]]
    assert floors == sorted(floors, reverse=True)

    remapped = _deep_copy_policy()
    remapped["confidence"] = {"bands": [{"name": "only", "min_score": 5}], "fallback": "none"}
    monkeypatch.setattr(locate, "POLICY", remapped)
    assert _confidence(4) == "none"
    assert _confidence(5) == "only"


# --------------------------------------------------------------------------------------
# isolated-index behaviour: determinism, negatives, drift
# --------------------------------------------------------------------------------------


def _ranked_scores(result: dict) -> list[tuple]:
    return [
        (loc["path"], loc["line"], loc["score"], tuple(loc["reasons"]), loc["confidence"])
        for loc in result["locations"]
    ]


def test_scoring_is_deterministic(isolated_index):
    index_repo("cann/runtime", source=MINI, commit="deadbeef")
    first = locate_one(CONTEXT_LINE)
    second = locate_one(CONTEXT_LINE)
    assert first["locations"], first
    assert _ranked_scores(first) == _ranked_scores(second)
    assert first["index_miss"] is False
    assert first["locations"][0]["path"].endswith("context.cpp")
    scores = [loc["score"] for loc in first["locations"]]
    assert scores == sorted(scores, reverse=True)


def test_negative_case_returns_index_miss_and_no_locations(isolated_index):
    index_repo("cann/runtime", source=MINI, commit="deadbeef")
    for line in (UNRELATED_LINE, FABRICATED_LINE):
        result = locate_one(line)
        assert result["locations"] == []
        assert result["index_miss"] is True


def test_min_score_is_the_explicit_negative_case_control(isolated_index):
    index_repo("cann/runtime", source=MINI, commit="deadbeef")
    record = parse_line(CONTEXT_LINE)
    assert locate_record(record)["locations"], "sanity: the positive line resolves by default"
    impossible = locate_record(record, min_score=10_000)
    assert impossible["locations"] == []
    assert impossible["index_miss"] is True


def test_result_limit_defaults_to_the_policy(isolated_index, monkeypatch):
    index_repo("cann/runtime", source=MINI, commit="deadbeef")
    record = parse_line(CONTEXT_LINE)
    assert len(locate_record(record)["locations"]) >= 1
    limited = _deep_copy_policy()
    limited["limits"]["default_result_limit"] = 1
    monkeypatch.setattr(locate, "POLICY", limited)
    assert len(locate_record(record)["locations"]) <= 1


def test_line_refresh_delta_comes_from_the_policy(isolated_index, monkeypatch):
    index_repo("cann/runtime", source=MINI, commit="deadbeef")
    drifted_line = (
        "[ERROR] ASCENDCL(9,python):2026-01-01-00:00:00.000.000 "
        "[src/acl/aclrt_impl/context.cpp:10]create context failed, flags=9"
    )
    drifted = locate_one(drifted_line)
    assert drifted["locations"]
    assert not any(reason.startswith("line_delta:") for reason in drifted["basis"]["refresh_reasons"]), drifted["basis"]

    strict = _deep_copy_policy()
    strict["line_refresh_delta"] = 1
    monkeypatch.setattr(locate, "POLICY", strict)
    strict_drift = locate_one(drifted_line)
    assert strict_drift["locations"]
    assert any(reason.startswith("line_delta:") for reason in strict_drift["basis"]["refresh_reasons"])
