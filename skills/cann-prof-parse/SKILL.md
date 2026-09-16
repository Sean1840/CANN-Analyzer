---
name: cann-prof-parse
description: >
  定位 msprof 或 torch_npu 解析问题：host 建树、device parse、任务关联、
  export、mindstudio_profiler_output、ASCEND_PROFILER_OUTPUT。Use when
  cann-prof-pipeline 判定解析，或 the user asks about 解析结果、timeline/csv/db
  不对、CANNExportParser、建树、batchId 关联、/cann-prof-parse.
  Not for missing PROF raw files (use cann-prof-collect). Not the first skill
  when the user only says 分析这份数据 (use cann-prof-pipeline).
---

# 解析定位

只在链路判定=解析，或用户已确认是解析产物问题时进入。先验：[msprof](../cann-prof-pipeline/references/docs/profiling/prior/msprof.md)、[pytorch](../cann-prof-pipeline/references/docs/profiling/prior/pytorch.md)。表关联：[msprof-db.md](../cann-prof-pipeline/references/docs/profiling/details/msprof-db.md)；timeline 连线：[timeline-flow.md](../cann-prof-pipeline/references/docs/profiling/details/timeline-flow.md)。

字段/导出不对时按 [analysis-chain.md](../cann-prof-pipeline/references/analysis-chain.md) **从外往里比**：交付件 → 中间 db（没有则临时解析拿到）→ 仅当中间有计算/拼接再比原始 db → 原始仍错再按 host/device 上到组件代码。中间 db 对、交付件错才是导出；中间已错不要先改 assembler。需要和 `cann-prof-pipeline` 一起安装。

## 跳转

- 原始 `host/data` 或 `device_*/data` 切片缺失 → **`cann-prof-collect`**（不要因没有 `all_file.complete` 就判采集；那是解析标记且未必落盘）
- 捞出的内容说明是上报漏了（如 type 未注册）→ **回 `cann-prof-pipeline`（上报）**
- 单行对代码 → `cann-log-locate`；尚未分流 → **`cann-prof-pipeline`**

PROF 内 → msprof；`ASCEND_PROFILER_OUTPUT` / Parser.log → pytorch。细节对不上改 `details/`。可改代码时 [version-and-fix.md](../cann-prof-pipeline/references/version-and-fix.md)。

## 输出

[report-template.md](../cann-prof-pipeline/references/report-template.md)。
