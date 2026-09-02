---
name: msprof-diagnose
description: >
  Split an msprof/MindStudio Profiler failure into component vs collect vs parse
  vs unsupported using a CANN-Analyze evidence pack. Use when the user mentions
  msprof, msprof.py, PROF_*, ascend_pt, ProfilingParser, CANNExportParser,
  mindstudio_profiler, 采集, 解析, timeline empty, or /msprof-diagnose.
  Not for writing new profiler features.
---

# msprof stage split

Load `cann-log-triage` if there is no evidence pack yet. Load `cann-log-locate` before citing source files.

User-facing split is **上报组件 / 采集 / 解析** (plus 不支持, plus 业务/环境). Name the owner of the current error. Never phrase ownership as “don’t look at X”. If the fault is not msprof, still push localization on the owning repo (path construction, missing files, next commands). Routing: [owners.md](references/owners.md), [owners.json](../../../catalogs/owners.json).

## What to analyze

Follow [log-priority.md](../cann-log-triage/references/log-priority.md). Users often ignore WARNING; many profiler warnings are normal empty probes.

- Start from **ERROR**, plus anything the user named (missing timeline, empty csv, unnamed API, flip count, …).
- Pull WARNING/INFO **on that same path** only (same type / file / channel / parser).
- Do not enumerate every `Can't find the db` / `Table … not found` / `No Events` / `already exists` as a separate problem. Group same-cause lines into one item.

Do not rely on a fix that landed **after** the dump. See [version-match.md](references/version-match.md). Reconstruct from dic/slices/`Report*` vs `RegTypeInfo` (or the matching driver channel). A later `git log -S` hit is optional confirmation only.

## Stages

Use this exclusive order. Details: [split-tree.md](references/split-tree.md).

1. **业务/环境** — GE/Runtime/业务在 PROF 出现前就 ERROR（安装包缺失、图初始化失败等）。找 ModuleName 对应仓，继续把路径、缺文件、配置追到可验证的下一步。
2. **上报组件** — 采集器在跑，但某模块没 `MsprofReport*`/`MsprofRegTypeInfo`，或上报时 buffer 未 init。RUNTIME→`cann/runtime` profiling_agent；GE/FE→`cann/ge`；HCCL→`cann/hccl`；APP/AscendProfiler→`Ascend/pytorch`。
3. **采集** — 上报有了或采集已 start，但 PROF 缺 `host_start`/`*.done`、磁盘拦截、device dump 条数明显少于 host。找 `cann/runtime` `src/dfx/msprof/collector`（包侧 `cann/oam-tools`）。
4. **解析** — dump 已完整。失败在 `msprof --export/--analyze` 或 `mindstudio_profiler_log` → `ascend/msprof` `analysis/`。失败在 `ascend_pt/logs/*Parser.log` 的 FWK/关联/TraceView（`ProfilingParser`、`FwkFileParser`、`RelationParser`、`TraceViewParser`）→ `Ascend/pytorch` `torch_npu/profiler/analysis/`。`CANNExportParser` 只是对 PROF 调 `msprof --export=on`：子进程失败跟 msprof；`msprof` 不在 PATH / toolkit 未 source 是环境。
5. **不支持** — 文档或日志写明该路径不采。标明能力边界，并给出文档/开关核对步骤。

If none fit: `unknown`. Do not guess an owner.

## Tool signals

`evidence.summary.signals` and per-record `signals` are hints, not a verdict. Combine them with the tree above.

## Output

```text
判定: 上报组件 | 采集 | 解析 | 不支持 | 业务/环境
责任方: <仓> <目录或模块>（当前报错由谁产生）
原因: ...
next: （现场可执行的核对，继续往下定位）
分析依据: repo @ commit ...
```

Copy `basis.disclaimer` from the evidence pack or locate output. If `refresh_needed`, tell the user the index may not match their CANN build and ask for version/tag before treating the conclusion as final. If the clone is newer than the dump, say so; still conclude from dump artifacts, not from a post-dump PR.

When the owning repo is identified, do not stop at log matching. Use an existing clone or ask to `index --bootstrap --repo <id>`, then read the source. A non-msprof fault still needs this code-level push.
