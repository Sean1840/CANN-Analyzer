# Ascend/pytorch 细节（可能变更）

对不上现场 dump / parser 日志时更新本页，不要改 `prior/pytorch.md`。

**路径：** `torch_npu/profiler/`（Python）、`torch_npu/csrc/profiler/`（C++）。

**aclprof 时序（profiler_mgr.cpp）**

- Init → `aclprofInit`
- Warmup → CreateConfig + Warmup
- Start → `aclprofStart`；CPU 则建 `FRAMEWORK/` + DataReceiver
- Stop → StopDataReceiver、`aclprofStop`、DestroyConfig
- Finalize → `aclprofFinalize`
- Python `finalize_trace` → `profiler_info.json` 或 `profiler_info_{rank}.json`，以及 `profiler_metadata.json`（不是 meta.json）

落盘根目录创建已改到 Start/Warmup（runtime 侧提交 `58c9e7f03`）。

**Parser 分流（`_parser_config.py` / `_parser_deps_config.py`）**

- 只 FRAMEWORK：TorchOp、TaskQueue、TracePre、TreeBuild；ONLY_FWK 下 Operator/Trace/Stack
- 调 msprof：`CANNExportParser`（`msprof --export=on --output={PROF}`）
- 依赖 CANN 结果：CANNTimeline、CANNAnalyze、Kernel、Integrate、Communication、完整 Operator/Trace、DbParser
- Relation：FRAMEWORK task queue + CANN timeline

**样本 FRAMEWORK：** `torch.op_mark`、`torch.op_range`。
