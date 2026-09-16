# CANN-Analyze

CANN / msprof / torch_npu profiler 的日志定位与故障分流。CLI 做收集和行号索引，**不写根因**；分析走 Agent skills。

用户要「分析这份 PROF / ascend_pt / plog」时，入口永远是 **cann-prof-pipeline**，不要一上来就 parse 或 collect。

## Skills

| Skill | 做什么 | 何时用 |
|---|---|---|
| `cann-prof-pipeline` | 看 PROF / `*_ascend_pt` / plog（或口头 drv `ret=`），把问题分到上报、采集、解析或业务环境 | 「分析这份数据」「timeline 空」「报了 EK/EE」`/cann-prof-pipeline` |
| `cann-prof-parse` | host 建树、device parse、任务关联、export、`mindstudio_profiler_output` | pipeline 判定解析，或 csv/timeline/db 结果不对 |
| `cann-prof-collect` | aclprof 启停、PROF host/device 落盘、ChannelReader、`all_file.complete` | pipeline 判定采集，或原始件缺失 |
| `cann-log-locate` | 一行 slog/plog 对到源码 path:line（含 INFO/DEBUG） | 「这行日志对应哪」`/cann-log-locate` |
| `cann-log-triage` | 盘点日志和 PROF 目录，打 evidence 包，不断言根因 | 「先看看有哪些 log」`/cann-log-triage` |
| `cann-analyze-eval` | 跑 golden 用例和 rubric | 评测 locate 有效性，不用于现场诊断 |
| `msprof-diagnose` | 已废弃，立刻转 `cann-prof-pipeline` | 旧入口兼容 |

pipeline 判定解析后必须进 parse，判定采集后必须进 collect。locate / triage 是底座，不是分析入口。

共享文档在 `skills/cann-prof-pipeline/references/`（分析链、报告模板、profiling 先验/细节、msprof DB 表关联、timeline 连线）。parse / collect 通过相对路径引用，npx 时请把 cann 技能一起装。

## 安装

```bash
npx skills add Sean1840/CANN-Analyzer --list
npx skills add Sean1840/CANN-Analyzer -g -y --all
```

npx 拷贝各 skill 目录。`cann-prof-pipeline` 带 `scripts/`（CLI + catalogs + 开箱 `sites.sqlite`）。其它 cann skill 依赖 pipeline 的 `references/`，请一起装。

仓内也可：

```bat
set PYTHONPATH=tools
python -m cann_analyze skills-install --target grok
```

Grok 可以把本仓加进 `~/.grok/config.toml` 的 `[skills].paths`（建议 ignore `data/`、`.grok/`）。

## CLI

开发改 `tools/cann_analyze`。`skills/cann-prof-pipeline/scripts/` 是 npx 副本，发版时与 `tools/`、`catalogs/` 对齐。

```bat
set PYTHONPATH=tools
python -m cann_analyze status
python -m cann_analyze collect <path>
python -m cann_analyze evidence <path> -o evidence.json
python -m cann_analyze locate --line "<plog 一行>"
```

或 `scripts\cann-analyze.cmd status`。

- `collect` 盘点文件，不拷 device 二进制。
- `evidence` = collect + parse + locate。
- `locate` 读 `catalogs/baseline/sites.sqlite`，**查询时不 clone**。miss 再用已有 clone：`index --repo <id> --source <用户确认的路径>`。
- 6 位错误码走 `catalogs/cann_error_codes.json`。

## 本地配置

源码 clone 路径写在 `~/.agent-skills/config.json` 的 `cann.repo_paths`，或本仓 `catalogs/repos.local.json`（已 gitignore）。**第一次缺了先问用户再写**，不要猜盘符。

```json
{
  "schema": "agent-skills.config.v1",
  "cann": {
    "repo_paths": {
      "ascend/msprof": "/path/to/msprof",
      "cann/runtime": "/path/to/runtime"
    }
  }
}
```

示例见 `catalogs/repos.local.json.example`。

## 布局

```text
tools/cann_analyze/     CLI（开发改这里）
catalogs/               仓表、错误码、开箱 sqlite
skills/                 Agent skills
  cann-prof-pipeline/   入口 + references + npx 用 scripts
  cann-prof-parse/
  cann-prof-collect/
  cann-log-locate/
  cann-log-triage/
  cann-analyze-eval/
docs/                   profiling 先验/细节（与 pipeline references/docs 同步）
eval/                   评测用例
data/                   本地索引/镜像，不入库
```

评测：仓根 `PYTHONPATH=tools python eval/run_eval.py`。
