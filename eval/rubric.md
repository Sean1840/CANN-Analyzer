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
python -m eval.run_eval
```

from repo root, with `PYTHONPATH=tools`. The runner scores the **tool**. Skill stage-split is scored only when `--agent-output <json>` is supplied; otherwise those metrics are `skipped`, not `fail`.

## Pass bar for a skill revision

A skill change is acceptable only if:

1. Tool metrics on committed cases do not drop.
2. New failure modes get a new case, not a prompt-only exception.
3. `no_verdict` stays 100% on the tool. Skills may propose hypotheses but must cite evidence pack locations.
