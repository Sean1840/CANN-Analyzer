# cann/runtime（采集 + ACL 上报）先验

**仓职责：** msprof 基础能力的 **采集实现** 和 ACL 层 API 打点。对外头在 `pkg_inc/profiling/`，实现在 `src/dfx/msprof/`。

**数据来源**

- Host 组件：`MsprofReportApi / Event / CompactInfo / AdditionalInfo`（ACL/GE/HCCL/本仓 runtime）。
- Device 硬件：drv 通道，本仓 `ChannelReader` 读 buffer。
- AICPU：device 侧 additional，经驱动通道或 host 自搬回到本仓落盘。

**流向**

```text
aclprofStart
  → 建 PROF_*/host 与 PROF_*/device_*
  → Host Report 线程：按类型写入 host/data
  → ChannelReader：DrvChannelRead → upload → device_x/data
aclprofStop
  → 刷缓冲、写采集侧 done（如 host_start.log.done、end_info.done）
```

**和别的仓边界**

- 解析、建树、export 不在本仓（msprof）。
- 通道能不能 host-move 由 **driver** 在 start 参数里决定。
- ACL API 时间线由本仓 `prof_reporter` 上报，算 **上报** 不是采集落盘逻辑。
