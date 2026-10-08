# Locator standards (what the tool promises, and how it is measured)

The locator is the only part of this repo that produces a *number* an agent will trust:
the match score and the confidence band attached to it. This document fixes what those
numbers mean, which thresholds are contractual, and where the measured baseline lives.
Nothing here is a root-cause claim; the tool still only reports candidate code sites.

## 1. Scoring

Policy lives in [`../catalogs/locate_policy.json`](../catalogs/locate_policy.json) and is
loaded by `tools/cann_analyze/locate.py`. A missing or corrupt policy file degrades to
the same values shown here (no exception, no silent behaviour change).

| Signal | Effect on the score | Why it is weighted that way |
|---|---|---|
| `fingerprint` exact match | +50 | The normalised format string is the strongest identity a log line and a source call site share |
| `fingerprint` token overlap >= the configured floor | +`overlap_multiplier * overlap` | Near-identical wording across versions |
| log file basename == site basename | +40 | `file:line` in the log usually names the file, even across versions |
| log file path suffix matches | +20 (or +12 for an ageing/aging variant) | Disambiguates same-named files in different directories |
| line number identical | +20 | Same file *and* same line: almost certainly the same revision |
| line number within the tolerance (default 15) | +10 | Small drift between the snapshot and the field build |
| level identical | +4 | Weak corroboration only |
| error code appears in both | +15 | `E1xxxx`-style codes survive refactors better than wording |
| slog module hint matches the module in the catalog | +10 | Confirms the component |

A candidate must reach `min_score` (currently **25**) to be returned at all. Scores are capped
by the sum of the applicable signals; ordering is by score, ties broken by the query order in
`locate_record`. The floor was raised from 20 after calibration: at 20 a generic
`malloc failed, size=4096` line was admitted by token overlap alone, while every labelled
positive scores >= 70 (see [`../eval/rubric.md`](../eval/rubric.md), decision record).

## 2. Confidence bands

| Band | Score | How an agent should treat it |
|---|---|---|
| `high` | >= 80 | Treat as the code site. Cite `repo_id @ commit` plus `indexed_at`. |
| `medium` | >= 50 | Usable, but say which signals matched; prefer confirming by reading the file. |
| `low` | >= 25 | Hypothesis only. Do not present as the location. |
| `weak` | < 25 | Unreachable while `min_score` is 25; declared so an override still gets a stable label. |

`basis.refresh_needed` is raised when the reported line drifts more than
`line_refresh_delta` (default 20) from the index, or when the hit depends on a filename
variant, or when nothing was hit at all. A report that ignores `refresh_needed` is
claiming version alignment the tool did not verify.

## 3. Acceptance targets

These are the operating points the locator is expected to hit on the committed labelled
set (`catalogs/eval/labeled_cases.json`). They are targets for *changes*, not gates that
block a prompt edit.

| Metric | Target | Measured (2026-10-08) |
|---|---|---|
| `hit@1` on positives | >= 0.80 | 13/14 = 0.9286 |
| `hit@3` on positives | >= 0.90 | 14/14 = 1.0000 |
| false-positive rate on negatives | <= 0.10 | 0/10 = 0.0000 |
| confidence monotonicity (within a record) | 100% | pass |
| evidence pack `no_verdict` | 100% | pass |

The cross-case monotonicity check ("worst `hit@1` score >= best rank 2..3 score") is reported
as **not satisfied** (70 < 76). The two numbers come from different messages with different
evidence maxima, so it is not evidence of broken ordering; it is kept in the report as a
documented cross-case property and must be read together with the per-record check.

Index quality targets (separate axis, measured by `cann-analyze coverage`):

| Metric | Target | Current (shipped baseline) |
|---|---|---|
| Baseline repos with an index | all `baseline: true` repos | 8 / 8, `coverage.blind_spots.baseline_not_indexed` empty |
| `func_coverage` overall | >= 0.80 | 0.9811 |
| C++ sites for entry-point repos (`ascend/msprof`, `cann/runtime`) | > 0 | 1805 and 5793 |

`func_coverage` is the share of indexed sites that carry an enclosing function name. It
matters because the function name is most of the context an agent gets from a hit.

## 4. Measured baseline

Reproduce with (from the repo root, offline — the shipped baseline index is what the CLI
uses out of the box):

```text
PYTHONPATH=tools python eval/run_eval.py --labeled
PYTHONPATH=tools python -m cann_analyze coverage -o coverage.json
```

| Anchor | Value |
|---|---|
| Measured | 2026-10-08 |
| Policy | `cann-analyze.locate-policy.v1`, `min_score` 25 |
| Policy hash (sha256, `notes` excluded) | `b494e0744a0acc282825a0544be2f7547ea68d970e0967e7078ae3f286f0789f` |
| Index | `catalogs/baseline/sites.sqlite`, sha256 (first 16) `769e57523afcc01d`, 8 snapshots / 38364 sites |
| Index composition | cpp 37211, python 1153, `func_coverage` 0.9811 |
| Labelled set | 14 positives, 10 negatives |
| Locator result | hit@1 0.9286, hit@3 1.0000, false positives 0.0000 |

### Rebuilding the shipped index

The baseline is a build artefact: it must be regenerated whenever the macro catalog or the
function-name extractor changes, otherwise `coverage` reports the covered components as
blind spots.

```text
python -m cann_analyze index --baseline          # needs a local clone per baseline repo
pwsh -File tools/rebuild_baseline.ps1            # clones into %TEMP%, rebuilds, cleans up
```

`tools/rebuild_baseline.ps1` shallow-clones the 8 baseline repos into
`%TEMP%\cann-analyze-baseline\repos`, writes a temporary `catalogs/repos.local.json`
(gitignored), rebuilds the baseline, prints the resulting coverage, then deletes both the
clones and the temporary mapping. Commit the changed `sites.sqlite` (and its copy under
`skills/cann-prof-pipeline/scripts/catalogs/`, via `scripts/sync_skills_payload.py`) together
with the catalog or extractor change that required it.


The same command with `--floor N` measures another operating point without editing the policy;
`--strict` turns "a negative hit or a positive miss" into a non-zero exit for whoever wants a
hard check; `--json` emits the full report.

## 5. Known limits (do not over-claim past these)

- The index only covers repos that were cloned and indexed; `coverage.blind_spots` is the
  authoritative list. A miss there is not a bug in the log, it is a missing index.
- No version-to-commit map exists. `basis` tells the agent which commit was indexed; if
  the field build differs, the hit may silently point at another revision.
- `func` is derived from a lightweight brace scan, not a compiler front end. Constructs
  it cannot attribute are left empty on purpose rather than guessed.
- Scoring is order-based, not probabilistic; the bands are policy, not measured
  probabilities.
- The labelled set is a smoke baseline (14 positives / 10 negatives, resolving into 2 of the
  8 indexed repos), not a statistical estimate of field accuracy.
