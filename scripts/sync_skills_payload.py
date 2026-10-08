"""Keep the npx-installed skill payload byte-identical to the canonical sources.

Canonical (edit these):
    tools/cann_analyze/          the CLI package
    catalogs/                    repo table, error codes, log macros, baseline index

Mirrored (generated, committed, never hand-edited):
    skills/cann-prof-pipeline/scripts/cann_analyze/
    skills/cann-prof-pipeline/scripts/catalogs/

`npx skills add <repo>` copies the skill directories as-is, so the skill must ship a
self-contained copy of the CLI and catalogs. That copy is the only reason these two
trees are duplicated; this script removes the hand-sync risk.

Usage (from repo root):
    python scripts/sync_skills_payload.py --check   # exit 1 when drifted (used by tests)
    python scripts/sync_skills_payload.py --write   # re-materialise the mirror
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# (canonical dir, mirrored dir) pairs. Order is stable for reporting.
PAIRS = (
    (ROOT / "tools" / "cann_analyze", ROOT / "skills" / "cann-prof-pipeline" / "scripts" / "cann_analyze"),
    (ROOT / "catalogs", ROOT / "skills" / "cann-prof-pipeline" / "scripts" / "catalogs"),
)

SKIP_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
SKIP_SUFFIXES = {".pyc", ".pyo", ".sqlite-journal", ".sqlite-wal", ".sqlite-shm", ".db-journal"}


def _relative_files(root: Path) -> list[Path]:
    out: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if set(path.parts) & SKIP_DIRS:
            continue
        if path.suffix in SKIP_SUFFIXES:
            continue
        out.append(path.relative_to(root))
    return out


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def compare(canonical: Path, mirrored: Path) -> dict[str, list[str]]:
    """Return {'missing': [...], 'extra': [...], 'differs': [...]} for one pair."""
    if not canonical.is_dir():
        return {"missing": [f"canonical dir absent: {canonical}"], "extra": [], "differs": []}
    canonical_files = {p.as_posix() for p in _relative_files(canonical)}
    mirrored_files = {p.as_posix() for p in _relative_files(mirrored)} if mirrored.is_dir() else set()

    missing = sorted(canonical_files - mirrored_files)
    extra = sorted(mirrored_files - canonical_files)
    differs = []
    for rel in sorted(canonical_files & mirrored_files):
        if _digest(canonical / rel) != _digest(mirrored / rel):
            differs.append(rel)
    return {"missing": missing, "extra": extra, "differs": differs}


def check() -> tuple[bool, dict[str, dict[str, list[str]]]]:
    report: dict[str, dict[str, list[str]]] = {}
    ok = True
    for canonical, mirrored in PAIRS:
        result = compare(canonical, mirrored)
        report[str(mirrored.relative_to(ROOT)).replace("\\", "/")] = result
        if any(result.values()):
            ok = False
    return ok, report


def write() -> None:
    for canonical, mirrored in PAIRS:
        if not canonical.is_dir():
            continue
        if mirrored.exists():
            shutil.rmtree(mirrored)
        shutil.copytree(
            canonical,
            mirrored,
            ignore=shutil.ignore_patterns(*SKIP_DIRS, "*.pyc", "*.pyo", "*.sqlite-journal", "*.sqlite-wal"),
        )
        print(f"synced {canonical.relative_to(ROOT)} -> {mirrored.relative_to(ROOT)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="report drift and exit 1 if any")
    group.add_argument("--write", action="store_true", help="rewrite the mirrored copies")
    args = parser.parse_args(argv)

    if args.write:
        write()
        return 0

    ok, report = check()
    if ok:
        print("skills payload is in sync with tools/ and catalogs/")
        return 0
    print("skills payload has drifted from the canonical sources:", file=sys.stderr)
    for target, result in report.items():
        for kind in ("missing", "extra", "differs"):
            for item in result[kind]:
                print(f"  {kind:8s} {target}/{item}", file=sys.stderr)
    print("\nrun: python scripts/sync_skills_payload.py --write", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
