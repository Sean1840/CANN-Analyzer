# msprof split tree

Exclusive checks, first match wins.

## component（非 profiling 业务/环境）

- Evidence pack modules in RUNTIME, ASCENDCL, GE, FE, HCCL, DRV, AICPU, OP, TBE, TS with ERROR **and** no PROF tree, or failure is install/init of GE/OPP
- Application failed before `host_start.log` exists
- AI Core Error / device lost / malloc / illegal address in slog, profiler files optional or absent
- 责任方：按 ModuleName 走 owners.json modules；继续追该仓的路径/配置/缺文件

## report（上报组件）

- PROF 或采集进程已起来，但 API/type 名字/打点缺失：`MsprofReportApi` 失败、`Failed to found str for type` 且 type_info_dic 里没有该 type
- Runtime `ReportProfApi` + `MSPROF_ERROR_UNINITIALIZE`：先看上报侧是否在采集 init 完成前打点
- 找谁：RUNTIME→cann/runtime profiling_agent；缺 type 名且 dic 文件在但没有该 id→上报仓（RegTypeInfo）

## collect

- `PROF_*` missing, or present without `host_start.log` / `end_info` / slice `.done`
- Messages: failed to start profiling, open device, MsprofInit, dump failed, available volume, FileAgeing
- host 有 N 条 flip/type，device 明显少且对应 `device_*/data` 文件空或过短
- `collection_host.log` / `collection_device_*.log` show collector abort
- 找谁：cann/runtime `src/dfx/msprof`（采集落盘）

## parse

- `all_file.complete` or slice `.done` present on the inner `PROF_*` tree
- **PROF 内部解析** — `PROF_*/mindstudio_profiler_log`、`msprof --export/--analyze`、dic/sqlite → `ascend/msprof` `analysis/`
- **ascend_pt 内的数据及处理流程** — `FRAMEWORK/`、`logs/*Parser.log`（含 `ProfilingParser` / `CANNExportParser` 编排）、Relation、TraceView、`ASCEND_PROFILER_OUTPUT/` → `Ascend/pytorch` `torch_npu/profiler/`。定位从 torch_npu profiler 业务走；走进 PROF 产物后再用上一行
- schema / version mismatch / `msprof_analysis.so` / dequeue data match failed / empty parser input while raw data exists
- Failures in `Ascend/msprof-analyze` after dump already exists
- Visualization-only failures in `Ascend/msinsight` after CSV/JSON/DB exist
- Parser WARNING that a table/db is missing is **not** a parse fault unless the user asked for that data or an ERROR points at it. See [log-priority.md](../../cann-log-triage/references/log-priority.md).

## unsupported

- Explicit "not support" / "unsupported" / "not implemented" for the requested profiling switch, graph mode, or chip
- Catalog/docs state the path has no profiler instrumentation

## unknown

- Missing both slog and PROF tree
- Signals conflict and neither side has ERROR
- Index missing so locations are unverified — say so, then collect more files, do not pick a stage
