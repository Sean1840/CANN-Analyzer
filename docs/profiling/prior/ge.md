# cann/ge 先验

**仓职责：** 图编译/执行。Profiling 上只做 **host 上报**（节点/模型/host schedule），不落 PROF 目录。

**数据来源：** 图执行过程中的 node/model/tensor/step 等。

**流向**

```text
GE 执行 → MsprofReportCompactInfo / MsprofReportApi
        → runtime 采集 host/data
        → msprof 解析进 CANN 树（node/model 层）
```

**和别的仓边界**

- PROF 未起来就 GE ERROR → 业务/环境，不是采集。
- 树里缺 node/fusion、host 无对应 additional/compact 切片 → 本仓上报；切片在、树没建起来 → msprof 解析。
