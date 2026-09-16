# cann/driver 先验

**仓职责：** profiling **通道**。Device 硬件和（非自搬时的）AICPU 数据经 device drv ↔ host drv 到达 runtime 采集 buffer。

**数据来源**

- Device TS/硬件写入的 drv 通道
- AICPU 在非 host-move 时 `halProfSampleDataReport` 进同一类通道

**流向**

```text
device 写入通道 → host drv 可读 → runtime ChannelReader 读走 → PROF device_x/data
```

AICPU host-move：驱动在 start 时告知 device「host 提供了一块映射 buffer」，数据不再走 sample report 通道。是否启用由本仓在 **通道注册/start** 决定，采集仓只消费结果。

**和别的仓边界**

- 不解释 CANN API 树，不写 sqlite。
- 通道读失败、buffer 满、sample period：本仓 + runtime 采集；解析仓看不到原始切片就不要先改 parser。
