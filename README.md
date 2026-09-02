# CANN-Analyze

Thin CLI plus reusable Agent skills for CANN/Ascend logs. Collect any slog level, map lines to source via a **versioned log-site index**, and split msprof failures into 上报组件 / 采集 / 解析 (plus 不支持 and 业务/环境). Locate never clones a repo.

This is not a replacement for msprof, and the CLI does not emit a root cause. Agents read an evidence pack and apply the skills.

## Layout

| Path | Role |
|---|---|
| `tools/cann_analyze` | CLI: `status` `catalog` `index` `collect` `parse` `locate` `evidence` `skills-install` |
| `catalogs/` | Repos, slog modules, log macros, owners, msprof signals |
| `skills/` | Canonical SKILL.md for Grok / Claude / Codex / other agents |
| `eval/` | Golden cases and rubric |
| `docs/` | Architecture and index design |
| `data/indexes/` | Generated SQLite snapshots (not source) |
| `data/mirrors/` | Optional shallow clones from `index --bootstrap` (not source) |

## Requirements

- Python 3.10+
- Existing local clones of the repos you want indexed (at least `cann/runtime` and `Ascend/msprof` for msprof work)

From the repo root:

```bat
set PYTHONPATH=tools
python -m cann_analyze status
```

On Windows you can also use `scripts\cann-analyze.cmd` (it sets `PYTHONPATH`).

```bat
scripts\cann-analyze.cmd status
```

## Index (offline)

slog already embeds `[File:Line]`. Line numbers still drift across CANN versions, so searching HEAD for an old log is wrong. Index a clone you already have; store `(repo, commit)` call sites. Query is local SQLite only.

Pass `--source`, or copy `catalogs/repos.local.json.example` to `catalogs/repos.local.json` (gitignored):

```bat
python -m cann_analyze catalog
python -m cann_analyze index --repo cann/runtime --source <path-to-runtime>
python -m cann_analyze index --repo ascend/msprof --source <path-to-msprof>
python -m cann_analyze status
```

`index --bootstrap` may shallow-clone missing catalog repos into `data/mirrors/`. `locate` still never clones.

If the clone is newer than the dump, say so in the analysis. Diagnose from dump artifacts and the code that could have produced them. A fix commit that landed after the dump is optional confirmation only.

## Collect and locate

```bat
python -m cann_analyze collect <log-or-PROF-dir>
python -m cann_analyze evidence <log-or-PROF-dir> -o evidence.json
python -m cann_analyze locate --line "[ERROR] ASCENDCL(1,python):2026-09-02-18:11:41.000.000 [context.cpp:5]create context failed, flags=1"
```

`collect` inventories files; it does not copy device binaries. `evidence` is collect + parse + locate.

## Skills

Canonical copies live in `skills/`. Install into an agent directory:

```bat
python -m cann_analyze skills-install --target grok
python -m cann_analyze skills-install --target project-grok
python -m cann_analyze skills-install --target all
```

| Skill | Use |
|---|---|
| `cann-log-triage` | Inventory logs / PROF trees; evidence pack |
| `cann-log-locate` | Log line → indexed `path:line` |
| `msprof-diagnose` | Stage split and owning repo |
| `cann-analyze-eval` | Golden-case scoring |

### What to treat as a problem

Evidence packs still parse every level. The **user-facing problem list is not that inventory**.

1. **ERROR** (and EVENT that names a failure or error code).
2. What the user asked (missing timeline, empty csv, unnamed API, …). Then only WARNING/INFO on **that same** type / file / channel / parser.
3. Do not walk every `Can't find the db` / `Table not found` / `No Events` / `already exists` as its own fault. Many profiler warnings are empty probes for switches that were off.

Name the owner of the current error. Do not phrase ownership as “don’t look at X”. Cite `repo @ commit` and `indexed_at` from the tool `basis` block.

msprof dump attribution (when you need it):

- Host: each reported type registers typeInfo `level-id-str`. `5000` is runtime, `5500` is HCCL.
- Device: `rts → drv(PROF_CHANNEL_*) → collector` under runtime `src/dfx/msprof`. Some files (for example netdev_stats) are collector + DCMI, not a driver channel.
- `ascend_pt` wraps the same inner `PROF_*` plus `FRAMEWORK/` (`torch.op_mark`). typeInfo and driver channels apply only to `PROF_*`. FWK parse lives in `Ascend/pytorch` `torch_npu/profiler/analysis/`. `CANNExportParser` is `msprof --export=on` on that PROF tree.

## Eval

```bat
python eval/run_eval.py
```

Rubric: `eval/rubric.md`. The tool must not write `root_cause` / `verdict` / `diagnosis` into evidence JSON.

## Add a repo

1. Add `id` / `url` / `index_globs` / `modules` in `catalogs/repos.json`. Clone paths go in `catalogs/repos.local.json`, not in the shared catalog.
2. Update `catalogs/modules.json` and `log_macros.json` if the slog macros are new.
3. `python -m cann_analyze index --repo <id> --source <clone>`.
4. Do not change locate logic for a new repo.

Community snapshot: `python -m cann_analyze catalog --refresh` writes `catalogs/community_repos.json` from the GitCode public API. Indexed work uses `catalogs/repos.json`. If an API needs a token, set `GITCODE_TOKEN` in the environment. Do not put a PAT in the repo or in chat.

## What stays out of git

Already ignored: `data/indexes/`, `data/mirrors/`, `*.sqlite`. Also keep out:

- Field PROF trees, plog, zip dumps
- Evidence JSON from real tickets
- Installed skill copies under `.grok/` (edit `skills/` instead)
- Tokens and `catalogs/repos.local.json`

Design notes: [docs/architecture.md](docs/architecture.md), [docs/index-design.md](docs/index-design.md).
