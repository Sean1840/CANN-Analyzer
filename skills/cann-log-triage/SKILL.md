---
name: cann-log-triage
description: >
  收集并盘点 CANN/Ascend 日志（ERROR/INFO/EVENT/WARNING/DEBUG）和 PROF 目录，
  生成 evidence 包。Use when the user asks for 日志收集、盘点 plog/slog、
  evidence pack、有一堆 log 先看看有什么文件, or /cann-log-triage.
  Also used internally by cann-prof-pipeline. Not the entry for 分析这份
  profiling 数据 (use cann-prof-pipeline). Not for mapping one line to
  source (use cann-log-locate).
---

# CANN 日志收口（底座）

只做收集和分级盘点，不断言根因。Profiling 故障入口是 `cann-prof-pipeline`。

```text
python -m cann_analyze collect <path>
python -m cann_analyze evidence <path> -o evidence.json
```

解析 **全部级别** 进包。对外列问题仍 ERROR 优先，WARNING/INFO 只跟当前路径。plog 格式见 [log-format.md](../cann-prof-pipeline/references/docs/log-format.md)。仓内工具在 `tools/`，npx 后在 `cann-prof-pipeline/scripts/`。

收完若用户要定位 profiling：把 evidence 交给 `cann-prof-pipeline`。只要对某一行代码：`cann-log-locate`。
