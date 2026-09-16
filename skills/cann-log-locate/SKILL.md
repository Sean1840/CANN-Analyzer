---
name: cann-log-locate
description: >
  把 slog/plog 一行对到源码 path:line（含 INFO/DEBUG/WARNING）。Use when the user
  asks 定位代码、这行日志对应哪、file:line、行号漂移、fingerprint, or
  /cann-log-locate. Used internally by pipeline/parse/collect.
  Not for 分析整份 PROF/ascend_pt (use cann-prof-pipeline).
---

# 日志对源码（底座）

```text
# 仓内 PYTHONPATH=tools；npx 后指向 cann-prof-pipeline/scripts/
python -m cann_analyze locate --line "<raw>"
python -m cann_analyze locate <logfile>
python -m cann_analyze status
```

基线 sqlite 开箱；miss 则 `index --repo --source <用户确认的 clone>`。禁止为查行号 clone，也禁止自行猜测源码路径（例如某盘 `Code\msprof`）。用户给出路径后写入 `~/.cann-analyze/config.json` 的 `repo_paths` 或 `catalogs/repos.local.json`，以后按配置用。所有级别都能对。6 位错误码带 title/仓（`cann_error_codes.json`）。

不要做上报/采集/解析分流——那是 `cann-prof-pipeline`。
