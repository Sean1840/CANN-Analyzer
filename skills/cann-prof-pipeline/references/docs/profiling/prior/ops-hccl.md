# cann/hccl、ops-* 先验

**cann/hccl：** 开源/算法侧。当前索引仓内 **没有** `MsprofReport*` 实现；host 上报在 **hcomm**。本仓不作为上报责任默认仓。

**ops-nn / ops-math / ops-cv：** 算子实现。当前 **没有** `MsprofReport*`。算子在 device 上的耗时/PMU 来自 **硬件通道 → 采集 → 解析**，不是 ops 仓上报。

缺 kernel/PMU：先看 device_x/data 和采集通道，再看 msprof device parser，不要先查 ops 仓 Report。
