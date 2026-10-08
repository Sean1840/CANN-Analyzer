# Testing and quality gates

This repo is a skills package: the shipped artefacts are the `skills/*/SKILL.md`
prompts plus the small CLI in `tools/cann_analyze`. The rules below are deliberately
light — a skills repo needs regression protection at the points where a silent failure
would send the agent down the wrong path, not a full CI matrix.

## What we do NOT add (decision, 2026-10)

- **No CI workflow files.** Nothing here needs a build matrix, and a red pipeline on a
  docs-first repo mostly trains people to ignore it. The checks below are expected to be
  run by the author before pushing (`python -m pytest tests -q`), and are cheap enough
  (under 2 s on the bundled index) that this is realistic.
- **No new gate that blocks prompt-only edits.** Skill wording changes are reviewed by
  reading them against `eval/rubric.md`, not by a linter.
- **No network-dependent test.** A test must pass with no clones and no internet: the
  bundled `catalogs/baseline/sites.sqlite` and `fixtures/` are the only inputs.

If the repo later grows real users, the cheapest upgrade path is: run
`python -m pytest tests -q` plus `python eval/run_eval.py` on pull requests. Both are
already offline and bounded.

## What is covered by unit tests (the gates that matter)

| Business-critical path | Why it must not regress silently | Test |
|---|---|---|
| Log line parsing, all 6 formats | A mis-parse cascades into wrong level/module/pid and every later judgement | `tests/test_parse.py` |
| Fingerprint normalisation | Numbers/paths/printf collapsing is what makes cross-version matching work; over- or under-normalising silently changes hit rate | `tests/test_fingerprint.py` |
| Log site extraction (macro/function/level/fmt) | The index is generated code; a bad extractor produces a plausible but wrong index | `tests/test_extract_func.py`, `tests/test_extract_locate.py` |
| Locate scoring, bands, negatives | The score is the tool's only "confidence" statement; boundaries must map exactly as documented | `tests/test_locate_policy.py` |
| Locate policy loading and fallback | A missing/corrupt policy file must degrade to the documented defaults, never raise | `tests/test_locate_policy.py` |
| pid binding (ascend_pt / PROF / plog) | A wrong "related=true" lets the agent analyse two different processes as one | `tests/test_pid_bind.py` |
| Inventory caps and oversized files | "No data" and "too large to read" must not look the same to the agent | `tests/test_collect_caps.py` |
| Evidence pack caps | A truncated pack must say it is truncated | `tests/test_collect_caps.py` |
| Skill payload duplication | `npx skills add` ships `skills/cann-prof-pipeline/scripts`, which must stay byte-identical to `tools/` and `catalogs/` | `tests/test_payload_sync.py` |
| Repo catalog handling | Local clone paths merge correctly and unknown ids are left alone | `tests/test_catalog.py` |

Run everything:

```text
python -m pytest tests -q
```

## Duplicated payload (tools/ vs skill scripts/)

`npx skills add` copies skill directories verbatim, so `cann-prof-pipeline` must carry
its own copy of the CLI and the catalogs. The canonical sources are `tools/cann_analyze`
and `catalogs`; the copy under `skills/cann-prof-pipeline/scripts/` is generated.

```text
python scripts/sync_skills_payload.py --check   # non-zero when drifted
python scripts/sync_skills_payload.py --write   # re-materialise the copy
```

`tests/test_payload_sync.py` runs the `--check` path, so drift fails the test suite
instead of shipping a stale skill.

## Quantified locator standards

See [locator-standards.md](locator-standards.md) for the scoring policy, the confidence
bands, the acceptance targets and the measured baseline.
