# Baseline log-site index

`sites.sqlite` is the shipped snapshot of log call sites (file, line, keywords, format string) for:

`cann/runtime`, `ascend/msprof`, `cann/driver`, `cann/hccl`, `cann/hcomm`, `cann/ops-nn`, `cann/ops-math`, `cann/ops-cv`.

Rebuild after pulling those clones:

```bat
python -m cann_analyze index --baseline
```

Locate reads this file when `data/indexes/sites.sqlite` is absent. Re-index of a single repo writes the overlay, not this file.
