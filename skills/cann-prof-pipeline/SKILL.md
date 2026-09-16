---
name: cann-prof-pipeline
description: >
  Profiling 故障入口：分析 *_ascend_pt / PROF_* / plog，把问题分到上报、采集、
  解析或业务环境。Use when the user asks to 分析xxx数据、分析xxx日志、分析
  profiling、prof、msprof、ascend_pt、PROF_、plog、采集解析链路、timeline 空、
  csv/db 不符合预期、报了 EK/EE/EH 错、口头说 drv/ret= 记不清日志、或 runs /cann-prof-pipeline or
  /msprof-diagnose. Not for writing profiler features. Not for a single log
  line to source (use cann-log-locate). Not for only packing logs with no
  profiling dump (use cann-log-triage).
---

# 业务流程链路（Profiling 入口）

用户要分析 **profiling 数据或配套日志** 时只用本 skill 做分流。

先验：[overview](references/docs/profiling/prior/overview.md)、仓 `prior/*.md`、[error-codes](references/docs/profiling/prior/error-codes.md)。细节对不上 dump 就改 `details/`。msprof 表关联：[msprof-db.md](references/docs/profiling/details/msprof-db.md)；timeline 连线：[timeline-flow.md](references/docs/profiling/details/timeline-flow.md)。

工具：仓内 `PYTHONPATH` 指到本仓 `tools/`；npx 安装后指到本 skill 的 `scripts/`。然后 `python -m cann_analyze ...`。读实现才 clone；**源码路径第一次先问用户**，确认后写入 `~/.cann-analyze/config.json` 的 `repo_paths`（或 `catalogs/repos.local.json`）。禁止默认某盘符下的 Code 目录。

## 输入

| 项 | 规则 |
|---|---|
| 数据 | `*_ascend_pt` 或 `PROF_*`。有什么用什么 |
| 日志 | plog/slog 或粘贴。有什么用什么 |
| 现象 | 可选。也可以**只有口头**：模块（如 drv）+ 记不清的日志 + `ret=` / 错误码 |

缺一部分仍分析。只有口头、没有 plog/PROF 时：用错误码表和日志索引做**初步方向**，禁止编造 file:line；写清还要 plog（和 PROF，若在问采集/解析）。`ret=` 可能是采集 MsprofErrorCode（0–6）或驱动 DrvError；用户说 drv 则用 DrvError（`ret=16` → `DRV_ERROR_WAIT_TIMEOUT`）。

同时给了数据+日志时，**先看 `collect`/`evidence` 的 `pid_bind`**（规则见 [analysis-chain.md](references/analysis-chain.md)）。`related=false`：停止分析，告知用户 PROF/`info.json` 的 pid 与 plog 对不上，请换同一进程的材料。ascend_pt 被改名则不靠文件名判断 pid。

```text
python -m cann_analyze evidence <路径> -o evidence.json
python -m cann_analyze locate --line "<plog 一行>"
```

收材料时走 `cann-log-triage` 的 collect/evidence；对行号走 `cann-log-locate`。二者不是入口。

## 跳转

| 判定 | 下一步 |
|---|---|
| 解析 | **必须** `cann-prof-parse`，且按 [analysis-chain.md](references/analysis-chain.md) 追到报错那条数据 |
| 采集 | **必须** `cann-prof-collect`，同样追到切片内容，不要停在缺文件名 |
| 上报 | 从已捞出的 level/type/模块对注册表；HCCL→hcomm。给改法并走 version-and-fix |
| 超出 profiling 链 | 不要出完整报告。写：和 profiling 无关，建议找 xx 组件 |
| 只要对某一行到代码 | `cann-log-locate` |

分流见先验 overview。交付件字段不对时按 [analysis-chain.md](references/analysis-chain.md)：先比交付件和正常导出，再中间 db，再（有拼接才）原始 db，再 host/device 组件。可改代码时再 [version-and-fix.md](references/version-and-fix.md)。

## 输出

[report-template.md](references/report-template.md)。超出 profiling 链时不要套该模板全文。
