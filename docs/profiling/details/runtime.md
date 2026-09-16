# cann/runtime 细节（可能变更）

对不上 `host/data` 文件名或 aclprof 目录时更新本页。

**路径：** 实现 `src/dfx/msprof/`；对外 `pkg_inc/profiling/aprof_pub.h`、`prof_api.h`、`prof_common.h`。

**PROF 目录名**

`PROF_{6位序号}_{YYYYMMDDHHMMSSmmm}_{8位pid}{8位hash}` / `host` | `device_{id}`  
（`Utils::CreateProfDir` / `CreateResultPath`）

**Host 上报落盘**（`ReceiveData::DumpData`）

```text
{aging|unaging}.{api_event|compact|additional|variable}.{tag}[.slice_N]
```

API 的 tag 固定 `data`。Compact/Additional 的 tag 来自 `MsprofRegTypeInfo`。  
样本（mc2 l0）：`aging.api_event.data`、`aging.compact.task_track`、`aging.additional.mc2_comm_info`、`unaging.additional.hash_dic`、`unaging.additional.type_info_dic`。  
结束：同目录 `all_file.complete`；host 还有 `host_start.log.done`、`end_info.done`。

**ChannelReader**（`transport/prof_channel.cpp`）：`DrvChannelRead` 循环，满则 `UploaderMgr`。Job：`profimpl/collect/job_wrapper/`（`ProfAicpuJob`、`ProfTscpuJob`…）。

**ACL 上报：** `src/acl/common/prof_reporter.cpp` 析构 `MsprofReportApi`（`MSPROF_REPORT_ACL_LEVEL`）。

**AICPU device：** `collector/dvvp/msprof/devprof/src/devprof_drv_aicpu.cpp`（zhengkai）。`is_support_host_move` true → ring buffer；false → `halProfSampleDataReport`。
