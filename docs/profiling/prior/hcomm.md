# cann/hcomm（HCCL 上报）先验

**仓职责：** 集合通信。Profiling **上报实现在 hcomm**，不是 cann/hccl 仓。

**数据来源：** Host 集合通信 API、节点/MC2 通信域信息。

**流向**

```text
HCCL API / MC2 → ProfilingManagerPub（MsprofReport*）
               → runtime host/data（compact/additional）
               → msprof 建树 HCCL 层 + 与 device 通信任务关联
```

**和别的仓边界**

- 缺 HCCL host 切片 → hcomm 上报。
- 切片在、通信 timeline/关联错 → msprof（任务 id / batch）。
- 通信硬件计数在 device 通道，走 driver+采集，不走 Report。
