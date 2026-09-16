# cann_analyze

Profiling / plog 收集、行号索引、pid 对齐。被 `cann-prof-*` 与 `cann-log-*` 调用。npx 安装后本目录在 `cann-prof-pipeline/scripts/`。

```bash
set PYTHONPATH=<cann-prof-pipeline>/scripts
python -m cann_analyze --help
```

`catalogs/baseline/sites.sqlite` 是开箱日志点索引。miss 时对已有 clone：`python -m cann_analyze index --repo <id> --source <path>`。查询不会 clone。
