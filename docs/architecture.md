# Architecture

CANN-Analyze is a **thin tool + reusable skills**. The tool never diagnoses root cause. Agents consume an evidence pack and apply skills.

```text
user logs / PROF dir
        │
        ▼
   collect (inventory only)
        │
        ▼
   parse (ERROR/INFO/EVENT/WARNING/DEBUG)
        │
        ▼
   locate against versioned log-site index
        │
        ▼
   evidence pack JSON
        │
        ▼
   skills (triage / locate / msprof split)
```

## Why an index instead of cloning on each query

CANN slog already embeds `[FileName:LineNumber]`, and msprof Python logs embed `[file.py:line]`. Line numbers still drift across versions. Cloning `cann/runtime` or `Ascend/msprof` on every ticket is too slow and still wrong if HEAD is not the version that produced the log.

The index stores **log call sites**, not source trees:

- repo id, commit, path, line, function, macro, level
- format string and fingerprint (printf/numbers/paths collapsed)
- one source line of context

Query path is local SQLite only. `index` is an offline job against an existing clone (`local_path` in `catalogs/repos.json`). `locate` refuses to git clone.

## Versioning

Each snapshot is `(repo_id, commit)`. Prefer:

1. User-supplied `--commit` / CANN version hint from logs
2. Latest snapshot for that repo
3. Fingerprint match even when the logged line number is stale (`line_drift`)

Adding GE, HCCL, ops-nn, or a private fork is a catalog row plus `index --repo <id> --source <clone>`. Extractor macros live in `catalogs/log_macros.json`.

## Layers

| Path | Role |
|---|---|
| `tools/cann_analyze` | CLI: status, catalog, index, collect, parse, locate, evidence |
| `catalogs/` | repos, slog modules, macros, msprof path/message signals |
| `skills/` | agent playbooks, agent-agnostic SKILL.md |
| `eval/` | golden cases and rubric |
| `data/indexes/` | generated SQLite, not source |

## Extending beyond msprof

msprof is the first consumer, not the schema. `msprof_roles` on a repo (`component` / `collect` / `parse`) is metadata. New product surfaces add a skill that reads the same evidence pack. Do not fork the locator.
