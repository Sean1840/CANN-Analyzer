"""Guard the duplicated skill payload.

`npx skills add` copies skills/cann-prof-pipeline as-is, so that skill ships its own
copy of the CLI (`scripts/cann_analyze`) and the catalogs (`scripts/catalogs`). Those
copies have drifted from the canonical `tools/cann_analyze` and `catalogs` before, so
this test fails the moment they diverge again — the UT is the gate, no CI job needed.

Fix drift with:  python scripts/sync_skills_payload.py --write
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SYNC_SCRIPT = ROOT / "scripts" / "sync_skills_payload.py"


def _load_sync_module():
    spec = importlib.util.spec_from_file_location("sync_skills_payload", SYNC_SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sync_script_exists():
    assert SYNC_SCRIPT.is_file(), "scripts/sync_skills_payload.py is the canonical sync entry point"


def test_skill_payload_matches_canonical_sources():
    module = _load_sync_module()
    ok, report = module.check()
    if not ok:
        lines = []
        for target, result in report.items():
            for kind in ("missing", "extra", "differs"):
                for item in result[kind]:
                    lines.append(f"  {kind:8s} {target}/{item}")
        pytest.fail(
            "skills payload drifted from tools/ and catalogs/; "
            "run: python scripts/sync_skills_payload.py --write\n" + "\n".join(lines)
        )


def test_mirror_targets_are_the_expected_paths():
    module = _load_sync_module()
    targets = {str(mirrored.relative_to(ROOT)).replace("\\", "/") for _, mirrored in module.PAIRS}
    assert targets == {
        "skills/cann-prof-pipeline/scripts/cann_analyze",
        "skills/cann-prof-pipeline/scripts/catalogs",
    }
