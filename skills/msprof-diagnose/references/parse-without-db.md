# Parse when sqlite is missing

Parse localization often needs intermediate sqlite (`host/sqlite`, `device_*/sqlite`). The dump may have no db (simplify wiped it, export skipped, or C path never wrote it). Do not stop as unknown.

## 1. Reproduce the db

Run the same export with Python (msprof `--export=on`, or the torch_npu parser that writes sqlite) into a temp dir. Check whether the ERROR / missing table still appears.

- **Reproduces** — treat as current parse logic; pull the parse repo and walk the code (see below).
- **Does not reproduce** — prefer **Python export vs C++ export** (`analysis/msparser` vs `analysis/csrc`). Name which path the field used and where they diverge (writer, schema, `MIN_RECORD_NUM`, optional processor). Then walk back: slice/dic vs parser vs export mode.

## 2. Bypass via deliverables

If sqlite cannot be rebuilt, use what was already exported:

- PROF: `mindstudio_profiler_output/msprof_*.json`, `msprof_*.db`, csv
- ascend_pt: `ASCEND_PROFILER_OUTPUT/trace_view.json`, `analysis.db`, `ascend_pytorch_profiler_*.db`, csv

Compare those to raw slices / `FRAMEWORK/` / typeInfo. Empty sqlite plus a populated json still localizes to the db writer, not “no data”.

## Ask before cloning

Parse-logic localization needs the owning clone and a file-by-file read. Ask the user first: local path, or `index --bootstrap --repo ascend/msprof` / `Ascend/pytorch`. Do not clone at query time. Locate still never clones.
