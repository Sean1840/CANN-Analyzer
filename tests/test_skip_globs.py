"""Tests for the skip/include glob predicates.

`should_skip` and `_match_any` decide which source files ever reach the index. They were
cleaned up (a dead loop with an inline import in one, a clearer prefix build in the other),
so this pins the semantics: the ORIGINAL implementation is restated here as a reference and
the two must agree on a matrix of real catalog globs and awkward paths.
"""

from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path

from cann_analyze.extract import SKIP_DIRS, should_skip
from cann_analyze.index_cmd import _match_any


def should_skip_before_cleanup(path: Path, skip_globs: list[str]) -> bool:
    """Reference: the pre-cleanup implementation, verbatim in behaviour."""
    posix = path.as_posix()
    if set(path.parts) & SKIP_DIRS:
        return True
    for glob in skip_globs:
        pattern = glob.replace("\\", "/")
        if Path(posix).match(pattern) or Path(posix).as_posix().endswith(pattern.rstrip("*")):
            continue
    for glob in skip_globs:
        if fnmatch(posix, glob.replace("\\", "/")) or fnmatch(posix, "*/" + glob.replace("\\", "/")):
            return True
        if glob.endswith("/**"):
            prefix = glob[:-3]
            if f"/{prefix}/" in f"/{posix}/" or posix.startswith(prefix + "/"):
                return True
    return False


# Globs taken from catalogs/repos.json (skip_globs of the baseline repos).
SKIP_SETS = [
    ["tests/**"],
    ["test/**", "third_party/**"],
    ["test/**", "tests/**", "opensource/**", "build/**", "output/**"],
    ["tests/**", "docs/**"],
    [],
]

PATHS = [
    "src/acl/context.cpp",
    "analysis/common_func/db_manager.py",
    "tests/test_thing.py",
    "tests/nested/deep/test_thing.py",
    "test/e2e/spec.py",
    "third_party/zlib/zutil.c",
    "build/CMakeFiles/x.cpp",
    "output/gen/y.py",
    "opensource/ffmpeg/a.c",
    "docs/zh/guide.md",
    "misc/tools/run.py",
    "src/tests_utils/helper.py",  # contains "tests" but is not the tests dir
    "src/build_helper.py",
    "example/demo.cpp",
    "stub/stub.cc",
    "__pycache__/mod.cpython-310.pyc",
    "include/a.h",
    "inc/b.h",
]


def test_cleanup_preserved_should_skip_semantics(tmp_path):
    for skip_globs in SKIP_SETS:
        for rel in PATHS:
            path = tmp_path / rel
            assert should_skip(path, skip_globs) == should_skip_before_cleanup(path, skip_globs), (
                rel,
                skip_globs,
            )


def test_should_skip_handles_directory_names_and_globs():
    root = Path("repo")
    assert should_skip(root / "tests" / "test_x.py", ["tests/**"]) is True
    assert should_skip(root / "tests" / "nested" / "deep" / "test_x.py", ["tests/**"]) is True
    assert should_skip(root / "src" / "tests_utils" / "helper.py", ["tests/**"]) is False
    assert should_skip(root / "src" / "a.cpp", ["tests/**"]) is False
    assert should_skip(root / "third_party" / "z.c", ["third_party/**"]) is True
    assert should_skip(root / "any" / "third_party" / "z.c", ["third_party/**"]) is True


def test_should_skip_covers_skip_dirs_without_any_glob():
    assert should_skip(Path("repo/__pycache__/a.py"), []) is True
    assert should_skip(Path("repo/build/a.cpp"), []) is True
    assert should_skip(Path("repo/src/a.cpp"), []) is False


# index_globs from catalogs/repos.json.
INCLUDE_SETS = [
    ["**/*"],
    ["analysis/**", "src/**", "misc/**"],
    ["src/**", "include/**", "pkg_inc/**"],
    ["msprof_analyze/**", "config/**"],
    [],
]


def test_match_any_semantics_on_catalog_globs():
    cases = [
        ("analysis/common_func/x.py", ["analysis/**", "src/**"], True),
        ("src/acl/x.cpp", ["analysis/**", "src/**"], True),
        ("misc/x.py", ["analysis/**", "src/**"], False),
        ("analysis", ["analysis/**"], True),  # the directory itself
        ("analysis/deep/x.py", ["analysis/**"], True),
        ("src/x.cpp", ["**/*"], True),
        ("anything", ["**/*"], True),
        ("x.cpp", [], True),  # empty glob list means "no filter"
        ("config/a.json", ["msprof_analyze/**", "config/**"], True),
        ("pkg_inc/base/dlog_pub.h", ["src/**", "include/**", "pkg_inc/**"], True),
    ]
    for rel, globs, want in cases:
        assert _match_any(rel, globs) is want, (rel, globs)
