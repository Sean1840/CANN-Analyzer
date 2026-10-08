# Skill and locator evaluation rubric

Canonical scoring for `eval/cases/*.json` and `python -m cann_analyze` evidence packs. Skills must not invent extra metrics.

## What is scored

| Metric | Owner | Pass |
|---|---|---|
| `parse_ok` | tool | Parsed level/module/file match the case `expect.parsed` fields that are present |
| `locate_hit@1` | tool | Top location `path` equals `expect.path`, or embedded file basename matches when index is absent |
| `locate_hit@3` | tool | Expected path appears in top 3 |
| `line_tolerance` | tool | `|got.line - expect.line| <= expect.line_tolerance` (default 15). Line drift still counts as hit if path+fingerprint match |
| `signal_hit` | tool | Each `expect.signals` value appears in record signals |
| `no_verdict` | tool | Evidence JSON has no `root_cause`, `verdict`, or `diagnosis` field |
| `basis_present` | skill | Final answer cites repo_id, commit, indexed_at from the tool `basis` block |
| `stage_split` | skill | Agent output `stage` is one of `component`, `collect`, `parse`, `unsupported`, `unknown` and matches `expect.stage` |
| `no_hallucination` | skill | Agent does not cite a file/repo outside `expect.allowed_repos` without labeling it as unverified |
| `latency_s` | tool | Locate a 200-line log file from index without git clone; fail if the case sets `max_latency_s` and it is exceeded |

## Case file shape

```json
{
  "id": "slog-embedded-path",
  "skill": ["cann-log-locate", "cann-log-triage"],
  "log": "fixtures/logs/slog_sample.log",
  "expect": {
    "parsed": {"level": "ERROR", "module": "ASCENDCL"},
    "path_suffix": "context.cpp",
    "line_tolerance": 15,
    "signals": [],
    "stage": "component",
    "allowed_repos": ["cann/runtime"]
  }
}
```

## How to run

```text
PYTHONPATH=tools python eval/run_eval.py
PYTHONPATH=tools python eval/run_eval.py --labeled
```

from repo root. The first command scores the committed `eval/cases/*.json` on a throw-away
index built from `fixtures/mini_repo`, and exits non-zero if any case fails. The second
command is the calibration report: it scores `catalogs/eval/labeled_cases.json` against the
shipped `catalogs/baseline/sites.sqlite` index and prints hit/false-positive rates, a
confidence-band breakdown, a monotonicity check, and the policy schema plus hash. It reports
but does not gate by default; add `--strict` to exit 1 on a negative hit or a positive miss,
and `--json` for the machine-readable report. `--floor N` re-runs the same set with the
minimum accepted score overridden, which is how a what-if operating point is measured.

Skill stage-split is scored only when `--agent-output <json>` is supplied; otherwise those metrics are `skipped`, not `fail`.

## Pass bar for a skill revision

A skill change is acceptable only if:

1. Tool metrics on committed cases do not drop.
2. New failure modes get a new case, not a prompt-only exception.
3. `no_verdict` stays 100% on the tool. Skills may propose hypotheses but must cite evidence pack locations.

## Quantified baseline (measured 2026-10-08)

Exact command, from the repo root, offline (no clone, no network; the shipped baseline index
is the one the CLI uses out of the box):

```text
PYTHONPATH=tools python eval/run_eval.py --labeled
```

Reproducibility anchors:

| Item | Value |
|---|---|
| Policy file | `catalogs/locate_policy.json` |
| Policy schema | `cann-analyze.locate-policy.v1` |
| Policy hash (sha256 of the effective policy, `notes` excluded) | `b494e0744a0acc282825a0544be2f7547ea68d970e0967e7078ae3f286f0789f` |
| Minimum accepted score (`min_score`) | 25 (raised from 20; see the calibration note below) |
| Index | `catalogs/baseline/sites.sqlite`, sha256 (first 16) `4548df11fb022fea` |
| Index content | 8 snapshots, 35666 sites |
| Labeled set | `catalogs/eval/labeled_cases.json`, 14 positives and 10 negatives |

Overall:

| Metric | Value |
|---|---|
| hit@1 | 13/14 = 0.9286 |
| hit@3 | 14/14 = 1.0000 |
| miss rate | 0/14 = 0.0000 |
| false-positive rate | 0/10 = 0.0000 |

Per confidence band. For positives the band is the one the matched location reported (a case
that missed would be counted under `none`); for negatives it is the band of the hit that made
it a false positive. With `min_score = 25` the `weak` band is unreachable for returned
locations, so no negative can be admitted by token overlap alone:

| Band | cases | hit@1 | hit@3 | miss | false positives |
|---|---|---|---|---|---|
| high (>= 80) | 9 | 9 | 9 | 0 | 0 |
| medium (>= 50) | 5 | 4 | 5 | 0 | 0 |
| low (>= 25) | 0 | 0 | 0 | 0 | 0 |
| weak (< 25) | 0 | 0 | 0 | 0 | 0 |
| none (no hit) | 0 | 0 | 0 | 0 | 0 |

Monotonicity:

| Check | Result |
|---|---|
| Every record returns locations in non-increasing score order | pass |
| Worst hit@1 score >= best score of a case matched only at rank 2..3 | fail (70 < 76) |

The cross-case check compares scores of different messages, so a failure here does not mean
the ranking is broken. The rank-1 case scoring 70 is `f-bracket-file-sample`
(`context.cpp:232`, basename plus path suffix, no fingerprint); the rank-2 case scoring 76 is
`p-file-ageing-alt-site`, which keeps a 0.89 fingerprint overlap. Their evidence maxima differ,
so the raw scores are not comparable across cases. The check is kept because it is the
documented cross-case property; read it together with the per-record ordering check above.

### Negative cases

Nine of the ten negatives retrieve no candidate at all, even with the score floor removed
(`min_score=0`): unrelated prose, lorem ipsum, a fabricated slog line for a non-existent file,
a Python traceback, a hex-only line, a CANN version banner, a cmake line, an application JSON
line, and a whole fixture log of unrelated text. For those cases the retrieval stage already
excludes everything, so the score floor is not the binding constraint.

The tenth negative was the reason the shipped floor moved:

| Case | Log line | At `min_score = 20` | At `min_score = 25` (shipped) |
|---|---|---|---|
| `n-generic-malloc` | `malloc failed, size=4096` | hit: `src/dfx/msprof/collector/avp/basic/json/json_parser.c:731`, score 20, confidence `weak`, reason `fingerprint_overlap:0.67` | no candidate retrieved (best score 20, 5 below the floor) |

The message has no file, module, or line, and no indexed site emits the `malloc failed, size=N`
shape, so the candidate was admitted by token overlap alone exactly at the old floor. Since the
whole `weak` range (20 to 24) was reachable only through `fingerprint_overlap`, the floor was
raised to 25 in `catalogs/locate_policy.json` (documented in that file's `notes`).

Decision record:

| Operating point | hit@1 | hit@3 | miss | false positives |
|---|---|---|---|---|
| `min_score = 20` (old) | 0.9286 | 1.0000 | 0.0000 | 1/10 = 0.1000 |
| `min_score = 25` (shipped, `PYTHONPATH=tools python eval/run_eval.py --labeled`) | 0.9286 | 1.0000 | 0.0000 | 0/10 = 0.0000 |

Nothing else in the labelled set moved: no positive's matched location scores below 76, and the
smallest score of any returned positive location is 70, so the new floor keeps a 45-point margin
on the weakest positive. `--floor N` still allows a what-if at other operating points without
editing the policy file.

Limitations of this baseline: 14 positives and 10 negatives, all 14 positives from 8 distinct
messages, and every positive resolves into 2 of the 8 repos in the shipped index
(`cann/runtime` and `ascend/msprof`). It is a smoke baseline that makes the current thresholds
visible, not a statistical estimate.
