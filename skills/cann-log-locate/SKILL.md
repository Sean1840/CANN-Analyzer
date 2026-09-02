---
name: cann-log-locate
description: >
  Map CANN/Ascend log lines to source sites using the versioned log-site index.
  Use when the user wants 定位代码, file:line from slog/plog, log fingerprint
  matching, line drift, or /cann-log-locate. Works for runtime, msprof, ge, hccl,
  ops-*, and any catalogued repo. Do not clone repositories at query time.
---

# Locate code from logs

## Tool

```text
python -m cann_analyze locate --line "<raw log line>"
python -m cann_analyze locate <logfile>
python -m cann_analyze status
```

`status` shows whether snapshots exist. If the target repo is not indexed, tell the user to run `index` **offline** against an existing clone. Never `git clone` as part of locate.

## Steps

1. Parse the line. Prefer embedded `[file:line]` (slog and most msprof Python logs already have it).
2. Read `locations[]` from the tool. Trust `confidence=high` when `fingerprint_exact` or `basename`+`line_exact`.
3. If `line_drift` is true, cite the **index** path:line, not the stale number in the log. Say the log was emitted from an older or newer snapshot.
4. If only `embedded` is present (no index hit), report file:line plus candidate repos from `module`, and request `index --repo <id>` for that version.
5. Quote `fmt` / `source_line` from the index. Do not open the full source tree unless the user needs surrounding code after a high-confidence hit.

## Ranking the tool already applied

Do not re-rank from scratch. You may drop hits below `low` confidence. You may not invent a path that is not in `embedded` or `locations`.

## Output

For each notable log line:

- raw / level / module
- embedded file:line
- top location: `repo_id@commit path:line` confidence reasons
- drift warning if any

Every answer MUST end with the tool's `basis.disclaimer` (or the same facts if you assembled them):

```text
分析依据：<repo_id> @ <commit前12位> (<ref>), indexed_at=<ISO时间>
```

If `basis.refresh_needed` is true, say so in plain language and ask the user for CANN/组件版本或对应 git tag，然后重新 locate。Do not present a drifted hit as if it were the exact source that produced the log.

## Boundaries

- Locate is not diagnosis.
- Adding a new repo is a catalog + index job, not a one-off clone in chat.
