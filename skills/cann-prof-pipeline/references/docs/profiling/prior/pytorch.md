# Ascend/pytorch（torch_npu profiler）先验

**仓职责：** 框架 profiler。对齐 torch.profiler API；NPU 侧通过 aclprof 打开 runtime 采集；自己写 FRAMEWORK；解析时再调 msprof export，并把框架树和 CANN 结果拼成用户交付件。

**数据来源**

- CPU/框架原始：本仓 C++ 写入 `*_ascend_pt/FRAMEWORK/`
- NPU/CANN 原始：aclprof 交给 runtime，落在同目录下 `PROF_*`
- 用户交付：本仓解析写出 `ASCEND_PROFILER_OUTPUT/`、`logs/`

**流向**

```text
profile.start
  → FRAMEWORK 接收线程开
  → aclprofInit/Start（采集 PROF）
profile.stop / finalize
  → 停 FRAMEWORK 接收、aclprofStop/Finalize
  → 写 profiler_info*.json（框架采集结束标志）
analyse
  → 仅 FRAMEWORK 的 parser
  → 和/或 调 msprof --export 再关联 CANN
  → ASCEND_PROFILER_OUTPUT
```

**和别的仓边界**

- 不实现 PROF 内 host/device 原始落盘（runtime）。
- 不实现 `mindstudio_profiler_output`（msprof 解析）。
- 缺 FRAMEWORK / profiler_info → 本仓采集收尾；缺 PROF 原始 → runtime；缺 CANN 导出 → msprof。
