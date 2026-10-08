"""Tests for `cann-analyze coverage`.

Coverage answers "why can't you find my log line": either the component is not in the
index at all, or its call sites were indexed without an enclosing function. The report
must add up and must list the components it cannot help with.
"""

from __future__ import annotations

import pytest

from cann_analyze.coverage import coverage_report
from cann_analyze.index_cmd import index_repo
from cann_analyze.paths import bundled_index_path, project_root


def _index_mini_repo(repo_id: str = "cann/runtime") -> None:
    index_repo(repo_id, source=project_root() / "fixtures" / "mini_repo", commit="coverage-test")


def test_report_shape_on_injected_index(isolated_index):
    _index_mini_repo()
    from cann_analyze.store import connect

    conn = connect(isolated_index)
    try:
        report = coverage_report(conn)
    finally:
        conn.close()

    assert report["schema"] == "cann-analyze.coverage.v1"
    assert report["totals"]["repos_indexed"] == 1
    assert report["totals"]["sites"] > 0
    assert "cann/runtime" in report["per_repo"]


def test_totals_add_up_on_injected_index(isolated_index):
    _index_mini_repo()
    from cann_analyze.store import connect

    conn = connect(isolated_index)
    try:
        report = coverage_report(conn)
    finally:
        conn.close()

    per_repo_sites = sum(v["sites"] for v in report["per_repo"].values())
    per_repo_empty = sum(v["func_empty"] for v in report["per_repo"].values())
    assert report["totals"]["sites"] == per_repo_sites
    assert report["totals"]["func_empty"] == per_repo_empty
    assert sum(report["levels"].values()) == per_repo_sites
    for stats in report["per_repo"].values():
        assert 0.0 <= stats["func_coverage"] <= 1.0
        assert stats["cpp_sites"] <= stats["sites"]


def test_unindexed_catalog_repos_are_reported_as_blind_spots(isolated_index):
    _index_mini_repo()
    from cann_analyze.store import connect

    conn = connect(isolated_index)
    try:
        report = coverage_report(conn)
    finally:
        conn.close()

    blind = report["blind_spots"]
    assert "cann/runtime" not in blind["catalog_not_indexed"]
    assert "cann/hcomm" in blind["catalog_not_indexed"]
    assert "cann/hcomm" in blind["baseline_not_indexed"], (
        "cann/hcomm is a baseline repo; with only the mini repo indexed it must be listed"
    )
    assert report["totals"]["repos_missing_from_index"] == len(blind["catalog_not_indexed"])


def test_bundled_baseline_is_self_consistent():
    if not bundled_index_path().is_file():
        pytest.skip("bundled baseline index is not present")
    report = coverage_report()
    assert report["index_source"] == "bundled"
    assert report["totals"]["sites"] == sum(v["sites"] for v in report["per_repo"].values())
    assert report["snapshots"], "a bundled baseline must record its snapshots"


def test_indexed_msprof_sites_include_the_cpp_layer():
    """Regression guard for the macro-catalog gap.

    msprof logs through bare ERROR/WARN/INFO/DEBUG macros. While those names were
    missing from catalogs/log_macros.json the bundled baseline held 912 python-only
    sites for ascend/msprof and zero C++ sites. After the catalog fix and a baseline
    rebuild (`python -m cann_analyze index --baseline`) the C++ layer must be present.
    """
    if not bundled_index_path().is_file():
        pytest.skip("bundled baseline index is not present")
    report = coverage_report()
    msprof = report["per_repo"].get("ascend/msprof")
    if msprof is None:
        pytest.skip("ascend/msprof is not part of the bundled baseline")
    assert msprof["cpp_sites"] > 0, (
        "ascend/msprof has no indexed C++ site; the baseline predates the bare-macro "
        "catalog entries or was built with an extractor that skips them"
    )


def test_function_coverage_of_the_baseline_meets_the_documented_target():
    """docs/locator-standards.md targets func_coverage >= 0.80 for the shipped index."""
    if not bundled_index_path().is_file():
        pytest.skip("bundled baseline index is not present")
    totals = coverage_report()["totals"]
    assert totals["sites"] > 0
    assert totals["func_coverage"] >= 0.80, (
        f"func_coverage={totals['func_coverage']} is below the documented 0.80 target; "
        "the function-name extractor or the baseline is stale"
    )
