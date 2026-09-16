# plog 标准日志格式

解析器以 **plog** 为主格式。现场 slog/plog 一行：

```text
[LEVEL] MODULE(pid,prog):时间 [src:line] [tid] message
```

| 字段 | 例 | 说明 |
|---|---|---|
| LEVEL | `ERROR` `WARNING` `INFO` `DEBUG` `EVENT` | 方括号 |
| MODULE | `ASCENDCL` `RUNTIME` `PROFILING` `HCCL` | slog 模块名 |
| pid,prog | `(123,python)` | 进程号、进程名 |
| 时间 | `2026-09-02-18:11:41.121.000` | `YYYY-MM-DD-HH:MM:SS.mmm.uuu` |
| src:line | `[src/acl/context.cpp:244]` | 可缺；有则用于行号索引 |
| tid | `[54308]` 或 `[tid:54308]` | 可缺；旧日志也可能把 tid 写在 message 里 `(tid:54308)` |
| message | `create context failed, flags=1` | 正文 |

示例：

```text
[ERROR] ASCENDCL(123,python):2026-09-02-18:11:41.121.000 [src/acl/aclrt_impl/context.cpp:244] [171] create context failed, flags=1
```

`cann_analyze parse/locate` 仍兼容旧行（无 `[tid]`、tid 写在正文里）以及 msprof Python / torch profiler 行。分析时优先按上表拆字段。
