# Timeline 连线（chrome://tracing flow）

官方：[Trace Event Format](https://docs.google.com/document/d/1CvAClvFfyA5R-PhYUmn5OOQtYMH4h6I0nSsKchNAySU)。Viewer 右上角打开 **Flow events**。

## chrome 约定

| 字段 | 含义 |
|---|---|
| `ph: "s"` | FLOW_START |
| `ph: "t"` | FLOW_STEP（中间站，msprof/torch_npu 基本不用） |
| `ph: "f"` | FLOW_END |
| `id` | 配对键（可再加 `cat`/`name`） |
| `bp: "e"` | 箭头绑在 enclosing slice 的结束侧 |
| `pid`/`tid`/`ts` | 落到哪条 `X`/`B-E` 切片上 |

## msprof

C：`cann_assembler` 出 `s`，`ascend_hardware_assembler` / `hccl_assembler` 出 `f`。Python：`viewer/association/host_connect_device.py`。

1. 起点 `s`：Host `Node@launch`（以及 memcpy_async / record/wait）。`cat=HostToDevice`。`id = connectionId << 32`（`ConnectionIdPool`，`CONN_OFFSET=32`）。HCCL 再拼 ctx：`(connectionId << 32) + context_id`。
2. 终点 `f` + `bp=e`：Device TASK / HCCL OP / MEMCPY，同一 `id`/`cat`。
3. Python 另有按 `(device, stream, task, batch, context)` 拼 80bit id 的 HostTask 连线。
4. mstx：`cat=MsTx`，`id=mark_id`。

DB 侧同一键：`CANN_API.connectionId` = `TASK.connectionId` = `COMMUNICATION_OP.connectionId`。见 [msprof-db.md](msprof-db.md)。

## torch_npu

不重画 HostToDevice，而是吃 msprof timeline JSON：

1. `combine_acl_to_npu`：按 `cat=HostToDevice` 配 `s`/`f`，用 **end 的 `pid-tid-ts`** 对上 kernel 的 `ph=X`，得到 `acl_ts → [kernel]`。
2. 再画自己的 flow（`_trace_event_manager.py`）：
   - `torch_to_npu`：`id=kernel.ts`，`cat=async_npu`，s 在 torch op、f 在 NPU kernel
   - `enqueue_to_dequeue`：`id=corr_id`，`cat=async_task_queue`
   - `fwdbwd`：前向/反向跨 tid

无 task queue：用 acl start 时间在 torch op 树 `match_self_torch_op`。有 queue：`corr_id` 绑 dequeue 与 kernel。

两端都带 `bp=e`。缺 HostToDevice 时会打 “no HostToDevice flow events”。
