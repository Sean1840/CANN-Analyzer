# Ascend/msprof 细节（可能变更）

对不上中间 sqlite 表、关联 ERROR、export 列时更新本页。

**Host 建树**

- Python：`mscalculate/cann/cann_calculator.py` + `cann_analysis_gear.py`（Root/ACL/Model/Node/Task/HCCL Gear）
- C++：`HostTraceWorker` → `EventGrouper`（host/data）→ 按 tid `TreeBuilder` → `TreeAnalyzer` → `CANNTraceDBDumper`

GroupTreeEvent 类型：Api、FusionOp(Additional)、NodeBasic/Attr(Compact)、Tensor、CtxId(Additional，**V6 跳过**)、HcclInfo(Additional)、TaskTrack(Compact)、HcclOp(Compact)。

**batchId（关联用，芯片相关）**

```text
非 V6: batch = taskId >> 16，task 低 16 位
V6:    batch = 0，task 32 位
```

四元组：`(streamId, taskId, contextId, batchId)`。`ascend_task_association.cpp`、`hccl_calculator.cpp`。Python 另有 `batch_counter.py`（GE iter）。

**Device parse → 关联**

`parser/parser_item/`（ACSQ、FFTS、PMU、flip、memcpy…）→ LogModeling → `LoadHostData`（读 host runtime db）→ `AscendTaskAssociation` → PMU association。

**import / export**

- Python：`msparser/` → sqlite → `mscalculate/` + `viewer/`
- C：CannParser/DeviceParser → processor + `application/summary|timeline/*_assembler.cpp`
- 配置：`msconfig/msprof_export_data_config.py`；拓扑：`timeline_topology_register.cpp`
- 混跑时中间仍是 sqlite；全 C 规划改内存
- Python 解析结束可能在 `data/all_file.complete` 落标记（`is_analyzed_data` 用来跳过再 parse）。C 化 WrapRunPipeline 看 sqlite 是否非空，**不一定写这个文件**。有无该文件不能单独判断采集或解析成败。

**样本 device_0/data：** `stars_soc.data`、`ts_track.data`（随开关变）。

**统一 DB 与 timeline 连线**

- 表字段和关联：[msprof-db.md](msprof-db.md)（`CANN_API.connectionId` ↔ `TASK` / `COMMUNICATION_OP`）
- chrome://tracing flow 与 HostToDevice / torch_to_npu：[timeline-flow.md](timeline-flow.md)
