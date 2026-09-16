# 总流向（先验）

```text
业务/框架 (torch_npu)
    │  host：MsprofReport* / 回调
    │  NPU：aclprofStart
    ▼
runtime 采集  ──写出──►  PROF_*/host/data     （host 组件上报 + host 采样）
                  └──►  PROF_*/device_x/data （device 硬件经 drv 通道）
    ▲                         │
    │                         ▼
GE / HCCL(hcomm) / ACL        msprof 解析
ops 一般不走 Report*           host 建树 + device parse
                              host↔device 按任务 id 关联
                              export → mindstudio_profiler_output
                                      │
torch_npu 再解析 FRAMEWORK + 上述结果 → ASCEND_PROFILER_OUTPUT
```

交付件字段不对时不要先猜仓：交付件 → 中间 db →（有拼接才比）原始 db → host/device 组件。取数用 Python 读原始，不编 C；计算逻辑（Python gear / C assembler）只对照、筛选，不当原始数据。

分流（缺原始件才是采集；交付件错先走上面这条）：

1. 业务 ERROR 出现在 PROF 还不存在之前 → 业务/环境。
2. `host/data` 或 `device_*/data` 缺、无采集侧 `host_start`/`*.done` → **采集**（runtime）。不要用 `all_file.complete` 判断采集（那是解析标记，且现行路径未必落盘）。
3. 原始在、缺 type 名或某类 host 切片 → **上报**（按模块：ACL/runtime、GE、hcomm）。
4. 原始完整、缺 `mindstudio_profiler_output` 或关联/导出错 → **解析**（msprof）。有无 `all_file.complete` 不能单独定解析成败。
5. PROF 已解析、缺 `ASCEND_PROFILER_OUTPUT` / `logs` → **框架解析**（pytorch）。
6. 解析过程发现原始条数/id 对不上 → 回到采集或上报，不要停在 viewer。

Device 硬件：TS/硬件 → device drv 通道 → host drv → 采集 buffer → `device_x/data`。  
Host 组件：进程内 Report，不经 drv。  
AICPU：同一套 additional 数据，回 host 可以走 **驱动通道** 或 **host 映射 buffer（采集侧自搬）**，由驱动在 start 时选择。
