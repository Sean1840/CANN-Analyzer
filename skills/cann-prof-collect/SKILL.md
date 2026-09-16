---
name: cann-prof-collect
description: >
  定位 profiling 采集落盘：aclprof 启停、PROF host/device data、ChannelReader、
  AICPU 通道、host_start/done。Use when cann-prof-pipeline 判定采集，or the user
  asks about 采集失败、原始件缺失、host_start、slice、aclprof、
  ChannelReader、/cann-prof-collect. Not for csv/timeline 解析结果
  (use cann-prof-parse). Not the first skill for 分析这份数据
  (use cann-prof-pipeline).
---

# 采集定位

只在链路判定=采集或原始落盘不完整时进入。先验：[runtime](../cann-prof-pipeline/references/docs/profiling/prior/runtime.md)、[driver](../cann-prof-pipeline/references/docs/profiling/prior/driver.md)。需要和 `cann-prof-pipeline` 一起安装。

缺文件或落盘异常时按 [analysis-chain.md](../cann-prof-pipeline/references/analysis-chain.md) 打开切片/看条数，不要只报文件名缺失。

## 跳转

- 原始已完整、问题在解析产物 → **`cann-prof-parse`**
- 切片在、内容说明是上报漏了 → **回 `cann-prof-pipeline`（上报）**
- 行号 → `cann-log-locate`；尚未分流 → **`cann-prof-pipeline`**

AICPU 自搬 vs 驱动通道见 `details/driver.md`（宏变了改 details）。

能给出代码改法时走 [version-and-fix.md](../cann-prof-pipeline/references/version-and-fix.md)。

## 输出

[report-template.md](../cann-prof-pipeline/references/report-template.md)。无 plog 也可根据目录给初步采集结论，并要补日志。
