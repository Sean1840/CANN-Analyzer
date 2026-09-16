# msprof 统一 DB（`msprof_{时间戳}.db`）

来源：msprof `docs/zh/user_guide/profile_data_file_references_db.md`。对不上现场表/列时对照 dump 更新本页。

时间 ns、内存 Byte、带宽 Byte/s、频率 MHz。名字类字段多数是 INTEGER，解 `STRING_IDS(id → value)`。类型走 `ENUM_API_TYPE` / `ENUM_MODULE` / `ENUM_HCCL_*`。

## 主关联

```text
CANN_API.connectionId  ──┐
                         ├── TASK.connectionId
COMMUNICATION_OP.connectionId ─┘
MSTX_EVENTS.connectionId ───── TASK.connectionId

TASK.globalTaskId ── COMPUTE_TASK_INFO
                  ── COMMUNICATION_TASK_INFO
                  ── COMMUNICATION_SCHEDULE_TASK_INFO
                  ── MEMCPY_INFO
                  ── TASK_PMU_INFO / SAMPLE_PMU_*

COMMUNICATION_OP.opId ── COMMUNICATION_TASK_INFO.opId
```

`connectionId` 是 host API → device 任务的原始键。timeline JSON 的 flow `id` 是它再编码后的展示键，见 [timeline-flow.md](timeline-flow.md)。

## 表职责

| 表 | 角色 | 关键键 |
|---|---|---|
| STRING_IDS | 字符串字典 | id → value |
| SESSION_TIME_INFO | 采集窗 | start/endTimeNs |
| NPU_INFO / HOST_INFO | 设备 / 主机 | deviceId / hostUid |
| CANN_API | Host CANN API（含 Node@launch） | connectionId、globalTid、name |
| TASK | Device 硬件任务 | globalTaskId、connectionId、stream/task/batch/context |
| COMPUTE_TASK_INFO | 计算算子描述 | globalTaskId → TASK |
| COMMUNICATION_OP | 通信大算子 | connectionId、opId |
| COMMUNICATION_TASK_INFO | 通信小算子 | globalTaskId、opId |
| MEMCPY_INFO | 拷贝量/方向 | globalTaskId |
| MSTX_EVENTS | Host mstx | connectionId → TASK |
| OVERLAP_ANALYSIS | 计算/通信重叠 | 独立时间片 |
| RANK_DEVICE_MAP | rank↔device（torch db） | 文档写 rankId 固定 -1 |

开关：TASK / COMPUTE_TASK_INFO 由 `--task-time`；CANN_API 由 `--ascendcl`；通信表由 `--task-time`/`--hccl`。
