# 异常样例定位报告（analyze/1–3）

aclGraph / aiv / mc2 不是本批故障样例。analyze/2 已收成 skill 有效案例：[type-1071-memset.md](../../cann-prof-pipeline/references/cases/type-1071-memset.md)。

---

## analyze/1

当前报错和 profiling 组件无关。建议找 **GE / FE（cann/ge）** 做进一步定位。

依据：`analyze/1/plog.txt` 仅有 GE 初始化失败（FE 读 `opp/built-in/fusion_rules/ai_core/built_in_graph_rules.json` 失败 → GraphOptimizer / GEInitializeV2 / ERR03005）。没有 PROF、没有采集。不要按 msprof 采集或解析继续扩。

---

## analyze/2

代码时间点: 中间 db `host/sqlite/api_event.db`；type 字典 `host/data/unaging.additional.type_info_dic`。`type_data.cpp:56` 基线未收录，行号以解析日志为准。

### 输入
- 数据：`analyze/2/c/result_dir` 两份 PROF
- 日志：`analyze/2/c/plog.txt` + `mindstudio_profiler_log`
- 现象：未提供

### 问题
解析报 `Failed to found str for type: 1071`。采集主干成功。

### 责任组件
**上报** — `cann/runtime`（Runtime API，level=5000 / ApiData.level=`runtime`）。  
Runtime 对 type **1071** 做了 `MsprofReportApi`，但 **没有** `MsprofRegTypeInfo`，所以 `type_info_dic` 里没有 `5000_1071:`。解析只是查字典失败。

### 证据（已从原始件和中间 db 核对）
- 解析日志上下文：先 `Typeinfo data load from path: .../host/data`，建树 Group Kernel 时 `type_data.cpp:56` 打 ERROR（每份 PROF 6 次，共 12 次）。
- 字典原文：`unaging.additional.type_info_dic.slice_0` 为文本 `level_type:name`。level 5000 有 `1063:KernelLaunchWithHandle`、下一条是 `1072:CpuKernelLaunch`，**没有 1071**。
- 中间 db：`host/sqlite/api_event.db` 表 `ApiData`，`struct_type='1071'` 且 `level='runtime'` **6 行**（起止时间、thread_id=2394278/2397243）。这就是 1071 的出处：Runtime 层 API 打点，不是 HCCL/GE。
- 原始 `aging.api_event.data.slice_0` 中 little-endian u32=1071 出现 6 次，与 db 行数一致。
- 采集完整：host_start.done、all_file.complete、mindstudio_profiler_output。plog 无 `[ERROR]`。
- 次要：plog `[WARNING] Channel is invalid, channelId:7`（DDR 通道本芯片无效），与 1071 无关。

### 来源
type_info_dic + api_event.db + 解析日志。未对齐本机基线版本。

### 为什么会出现
解析 `TypeData::Get(level, type)` 用 dic 把数字翻译成名字。Runtime 上报了 API type=1071，注册表跳号（1063 之后直接 1072），查不到就 ERROR，并把名字落成字符串 `"1071"`。交付件仍能出，只是这条 API 在树上没有可读名。

### 修改方案
1071 = `RT_PROFILE_TYPE_API_BEGIN(1000) + RT_PROF_API_Memset(71)`，名字应是 **Memset**。

在 `cann/runtime` `ProfilingAgent::RegisterProfTypeInfo` 的 `registerInfo[]` 中补：

```cpp
{RT_PROFILE_TYPE_API_BEGIN + RT_PROF_API_Memset, "Memset"},
{RT_PROFILE_TYPE_API_BEGIN + RT_PROF_API_MemsetAsync, "MemsetAsync"},
```

（MemsetAsync=1073，同一缺口。）不要改解析仓白名单当根因修复。

### 当前仓是否已改
**已合入 master。** runtime `c1ee3c3c2`（2026-08-13 19:35 +0800）xiachanglin：`【PR】: fix profiling type register`。

- GitCode：https://gitcode.com/cann/runtime/merge_requests/4201
- 描述原文：Memset/MemsetAsync 已 CallApiBegin 上报，RegisterProfTypeInfo 缺映射，解析只能看到数字。

本样例 PROF 时间 **2026-08-12**，**早于修复一天**。用含 `runtime!4201` 之后的包重采，`type_info_dic` 应出现 `5000_1071:Memset`，这条 ERROR 应消失。

请确认这份 analyze/2 跑的 CANN/runtime 包版本（日志路径是 910b 测试包）。若包日期 ≥ 2026-08-13 仍复现，再查该包是否没合 4201；不要在已修复的新仓上重复改。

### 分析链
采集完整 → 解析缺名 → runtime 漏注册 Memset(1071) → **仓内 2026-08-13 已修**。停止：升级到含 runtime!4201 的包验证。

---

## analyze/3

代码时间点: 中间 db `device_0/sqlite/netdev_stats.db`；原始 `device_0/data/netdev_stats.data.0.slice_0`。processor 行号以日志为准。

### 输入
- 数据：`analyze/3/result_dir/PROF_000001_20260902042751295_*`
- 日志：仅 `mindstudio_profiler_log`（无独立 plog）
- 现象：未提供

### 问题
export 报 NetDevStats 失败，并拖垮 Timeline / Summary；其它硬件 csv 仍有。

### 责任组件
**解析** — `ascend/msprof` `netdev_stats_processor.cpp`。原始 nic/netdev 切片在，采集不是空目录。失败原因是 **中间表只有 1 行，不够算差分**。

### 证据
- `netdev_stats_processor.cpp`：`ProcessData` 要求 `NetDevStatsOriginalData` **至少 2 行**（`MIN_RECORD_NUM=2`，用相邻时间戳做差值算速率）。`< 2` 则 `Get ... data failed`，`processedData.empty()` → `Format NetDevStats data error`，`Process()` 失败。
- `export_manager` / `py_init_parser` 把该失败当成 Timeline/Summary run failed（整段 export 失败码）。
- 中间 db 实测：`device_0/sqlite/netdev_stats.db` 表 `NetDevStatsOriginalData` **rows=1**（timestamp 一条，计数全 0）。
- 原始件：`device_0/data/netdev_stats.data.0.slice_0` **47 字节**，与「只采到 1 个采样点」相符。同目录 `nic.data` / `roce.data` 更大，所以网卡通道不是完全没采。
- 采集标志：host_start.done、all_file.complete 在；mindstudio_profiler_output 仍有 nic.csv 等（来自 **nic.db**，不是 NetDevStats 这条 processor）。

### 来源
原始 slice + sqlite 行数 + processor 源码。版本未对齐基线。

### 为什么会出现
NetDevStats 交付件是「相邻两次采样的差值」。一次短测/采样周期大于任务时长时，通道只落 1 个点。解析把「不够算差分」打成 ERROR 并让 Timeline/Summary 失败，属于 **解析对空/单点过于严格**；采集侧则是 **该通道采样点过少**（不是没开通道）。

### 怎么解决 / 继续定位
1. 确认不是采集丢文件：有 `netdev_stats.data` + `netdev_stats.db` 有表。
2. 数行：`SELECT COUNT(*) FROM NetDevStatsOriginalData` — 本样例为 1。
3. 两条路：
   - **解析**：`<2` 行应 skip（与 `CheckPathAndTable` 无表就跳过同类），不要让 Timeline/Summary 整段失败。改 `netdev_stats_processor.cpp` ProcessData。
   - **采集**：拉长业务或提高 netdev 采样频率，保证 ≥2 个点。
4. 无独立 plog 不影响本结论；若要查采样周期，再补采集期 plog 里 PROFILING/DRV 的 netdev 通道 start。

### 分析链
采集（netdev 只有 1 点）→ 解析差分失败 → export Timeline/Summary 失败。根因可同时记：解析容错不足 + 该通道采样过短。优先改解析 skip，采集按需加长。
