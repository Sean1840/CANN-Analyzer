# cann/ge、cann/hcomm 细节（可能变更）

上报文件路径变了就改本页。

**GE**

- `runtime/v2/subscriber/profiler/cann_profiler_v2.cc`：`MsprofReportCompactInfo`（NodeBasicInfo 等）+ `MsprofReportApi`
- `cann_host_profiler.cc`：host_sch `MsprofReportApi`

**HCCL**

实现在 **hcomm**（`ProfilingManagerPub::CallMsprofReportHostApi` / `Mc2CommInfo` / `NodeInfo`）。  
`op_base` 各集合通信入口包一层。`cann/hccl` 仓无 Report 实现。

样本 host 切片：`aging.additional.mc2_comm_info`。
