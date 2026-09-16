# 案例：解析报 type 1071 无名字（Runtime Memset 漏注册）

**材料：** `E:\Code\msprof_data\analyze\2`（PROF + plog）。PROF 时间 2026-08-12。

**怎么追（缺 type 名时照做）**

1. 解析日志：`Failed to found str for type: 1071`，上下文是加载 `host/data` 的 type_info 后建树。
2. 读 `unaging.additional.type_info_dic`（文本 `level_type:name`）。本例无 `5000_1071:`；5000 是 Runtime，1063=`KernelLaunchWithHandle`，下一条 1072=`CpuKernelLaunch`。
3. 中间 db：`host/sqlite/api_event.db` 表 `ApiData`，`struct_type=1071` 且 `level=runtime`（本例 6 行）。原始 `aging.api_event.data` 里 u32=1071 次数一致。
4. 对照 runtime：`1071 = RT_PROFILE_TYPE_API_BEGIN(1000) + RT_PROF_API_Memset(71)`。

**责任：** 上报 — `cann/runtime`。解析只是查字典失败。

**改法：** `ProfilingAgent::RegisterProfTypeInfo` 的 `registerInfo[]` 增加

```cpp
{RT_PROFILE_TYPE_API_BEGIN + RT_PROF_API_Memset, "Memset"},
{RT_PROFILE_TYPE_API_BEGIN + RT_PROF_API_MemsetAsync, "MemsetAsync"},
```

**仓内状态：** 已合入 master，`c1ee3c3c2`，2026-08-13。  
PR：https://gitcode.com/cann/runtime/merge_requests/4201  

**版本：** 本 dump 早于修复一天。含 `runtime!4201` 的包重采后 dic 应有 `5000_1071:Memset`，ERROR 应消失。用户包若已晚于该日仍复现，再查包是否未合 4201。
