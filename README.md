# CANN-Analyze

CANN / msprof / torch_npu profiler 的日志定位与故障分流。CLI 做收集和行号索引，**不写根因**；分析走 Agent skills，入口是 **cann-prof-pipeline**。

本仓是 cann 相关技能和工具的**唯一维护处**（已从 Agent-Skills 迁出）。

## 布局

| 路径 | 作用 |
|---|---|
| `tools/cann_analyze` | CLI（开发改这里） |
| `catalogs/` | 仓表、错误码、开箱 `baseline/sites.sqlite` |
| `skills/` | Agent skills（pipeline / parse / collect / locate / triage / eval） |
| `skills/cann-prof-pipeline/scripts/` | npx 用的 CLI+catalogs 副本，发版时与 `tools/`、`catalogs/` 对齐 |
| `docs/` | profiling 先验/细节（与 pipeline `references/docs` 同步） |
| `eval/` | 评测用例 |
| `data/` | 生成本地索引/镜像，不入库 |

## 命令

```bat
set PYTHONPATH=tools
python -m cann_analyze status
python -m cann_analyze collect <path>
python -m cann_analyze evidence <path> -o evidence.json
python -m cann_analyze locate --line "<plog 一行>"
```

或 `scripts\cann-analyze.cmd status`。

行号 miss：`index --repo <id> --source <用户确认的 clone>`。不要为查行号 clone，也不要猜盘符。路径写入 `~/.agent-skills/config.json` 的 `cann.repo_paths` 或 `catalogs/repos.local.json`。

## Skills

| Skill | 何时用 |
|---|---|
| `cann-prof-pipeline` | 分析这份数据/日志、口头 drv `ret=` |
| `cann-prof-parse` | 解析产物不对 |
| `cann-prof-collect` | 采集/原始 PROF 缺文件 |
| `cann-log-locate` | 一行日志对 path:line |
| `cann-log-triage` | 先盘点日志 |
| `cann-analyze-eval` | 评测，不用于现场 |

```bash
npx skills add Sean1840/CANN-Analyzer -g -y --all
python -m cann_analyze skills-install --target grok
```

Grok 可把本仓加进 `~/.grok/config.toml` 的 `[skills].paths`。

## 本地配置

机器路径和 GitCode token 见 Agent-Skills 的 `gitcode-review/references/local-config.md`。cann 源码路径：`cann.repo_paths`。首次缺了先问用户再写 `~/.agent-skills/config.json`。
