---
name: cann-log-triage
description: >
  Collect CANN/Ascend logs of any level (ERROR, INFO, EVENT, WARNING, DEBUG),
  inventory slog/plog/device/msprof files, and produce an evidence pack for
  later location and analysis. Use when the user provides logs, ascend/log,
  PROF_* dirs, plog, slog, dlog, EVENT logs, or asks for 日志收集/问题定位准备.
  Also use for /cann-log-triage. Do not use for writing new operators or building CANN.
---

# CANN log triage

Generic entry for any CANN/Ascend repo. Read logs first. Do not clone source during triage.

## Tool

From the CANN-Analyze repo, with `PYTHONPATH=tools`:

```text
python -m cann_analyze collect <log-or-dir>
python -m cann_analyze evidence <log-or-dir> -o evidence.json
```

If the working copy is this repo, `scripts/cann-analyze.cmd evidence <path>` is equivalent.

## Steps

1. Take whatever the user already has: a file, `$HOME/ascend/log`, a `PROF_*` tree, stdout, or pasted lines. Do not ask them to re-run collection unless the inventory is empty.
2. Run `collect` then `evidence`. Parse **all** levels into the pack (later “why is xxx missing” needs INFO/WARNING). Analysis still follows [log-priority.md](references/log-priority.md): **ERROR first**, then the user’s question, then only related WARNING/INFO.
3. Use `summary.levels`, `summary.modules`, `summary.signals`, `summary.top_repos`, `version_hints`.
4. Hand off location to `cann-log-locate` using the same evidence pack.
5. If the user mentioned msprof / profiling / parse / collect, also load `msprof-diagnose`.

## Output

Return:

- inventory (kinds of files found)
- notable records: **ERROR** (and failure EVENT) first. Include WARNING/INFO only when they sit on an ERROR or on a gap the user named. Do not list the full WARNING inventory as problems (see [log-priority.md](references/log-priority.md)).
- signals only as labels: `component` / `collect` / `parse` / `unsupported`
- next command: `locate` or `index` if snapshots are missing
- 分析依据：`evidence.basis.disclaimer`（仓 / commit / 索引时间）。`refresh_needed` 为 true 时，要求用户提供现场版本后再分析。

## Boundaries

- Do not clone gitcode.com during this skill.
- Do not emit a root cause. The evidence pack has locations and signals only.
- Parse every slog level (`[Level] Module(pid,pname):time [file:line]message`). Do not promote every WARNING into a problem; see [log-priority.md](references/log-priority.md).
