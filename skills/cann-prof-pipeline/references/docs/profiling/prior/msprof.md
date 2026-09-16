# Ascend/msprof（解析）先验

**仓职责：** 读 PROF 原始件，host 建树、device 解析、按任务 id 关联、export 交付件。不采集、不调 drv。

**数据来源**

- `PROF_*/host/data`：host 上报切片
- `PROF_*/device_*/data`：硬件/TS/AICPU 落盘
- 解析中间：host/device 下 sqlite（Python/C 混跑时的交接）

**流向**

```text
import/parser
  host/data  → 按线程分组 → 建树 → host sqlite
  device/data → device parser → device 任务/PMU
association
  host 任务  ↔  device 任务（同一套任务 id）
export
  calculator/viewer（或 C processor+assembler）
  → mindstudio_profiler_output、msprof_*.db
```

**和别的仓边界**

- 原始缺/坏：回 runtime 采集或上报仓，不要改 viewer。
- id 对不上：先查关联用的任务 id 是否同一套（含 batch），再查采集切片是否缺。
- torch_npu 的 `ASCEND_PROFILER_OUTPUT` 不在本仓。

交付件：`mindstudio_profiler_output` 的 json/csv，以及 `msprof_{时间戳}.db`（表关联见 [details/msprof-db.md](../details/msprof-db.md)）。Host→Device 连线见 [details/timeline-flow.md](../details/timeline-flow.md)。
