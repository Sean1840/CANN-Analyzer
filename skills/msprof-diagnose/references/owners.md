# Who to ping

After the stage split, always name a repo and a person-role. A WARNING is not automatically a problem; see [log-priority.md](../../cann-log-triage/references/log-priority.md).

Read the tables in [owners.json](../../../catalogs/owners.json). This file only states how to apply them.

## Order

1. If GE/Runtime/业务 already ERROR before PROF exists → **非 profiling**，按 ModuleName 找业务仓。
2. Else if dump 不完整 / collector init 失败 → **采集**，找 `cann/runtime` `src/dfx/msprof`（落盘）。
3. Else if dump 完整且失败在解析 → **解析**。PROF 内部 → `ascend/msprof` `analysis/`；ascend_pt 内数据与处理流程 → `Ascend/pytorch` `torch_npu/profiler/`。
4. Else if dump 在、解析只是缺名字/缺一类数据 → 先问 **上报组件** 有没有 `MsprofRegTypeInfo` / Report*，再问采集有没有把那份 dic 落盘。

## Phrasing

```text
判定: 上报组件 | 采集 | 解析 | 不支持 | 业务/环境
责任方: <仓> <目录>（<角色>）
原因: ...
next: ...
```

Name the owner of this error. Do not add “don’t look at …” lines.
