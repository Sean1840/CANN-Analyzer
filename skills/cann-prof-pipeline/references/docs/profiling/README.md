# Profiling 知识库

给 `cann-prof-pipeline` / parse / collect 和 `cann-log-*` 用。分两层，不要混。

| 层 | 目录 | 写什么 | 何时改 |
|---|---|---|---|
| **先验** | `prior/` | 数据从哪来、往哪流、责任落在哪仓 | 产品分层变了才改 |
| **细节** | `details/` | 文件名、函数、芯片宏、bit 切分、表名 | **可能随时变**。结论和日志/中间件对不上时，对照 dump 手动更新（处理方式同基线 sqlite：先用现成记录，对不上再刷新） |

业务 skill：`cann-prof-pipeline`（入口）→ `cann-prof-parse` / `cann-prof-collect`。`cann-log-locate` / `cann-log-triage` 是底座。未到无法定位就沿业务链追数据（[analysis-chain.md](../../analysis-chain.md)）。给改法后查仓是否已合入并对齐用户包版本（[version-and-fix.md](../../version-and-fix.md)）。msprof 统一 DB：[details/msprof-db.md](details/msprof-db.md)。timeline 连线：[details/timeline-flow.md](details/timeline-flow.md)。

分析时：

1. 只用先验判断 **上报 / 采集 / 解析 / 业务** 和数据方向。
2. 定位到仓之后，用该仓 `details/` 对现场 `PROF_*/host/data`、sqlite、plog。
3. 细节对不上：更新 `details/`，不要为迁就旧细节改分流结论。
4. 行号/关键字：`catalogs/baseline/sites.sqlite`；miss 再 `index --repo`。读实现才 clone。

按仓：

| 仓 | 先验 | 细节 |
|---|---|---|
| Ascend/pytorch（torch_npu） | [prior/pytorch.md](prior/pytorch.md) | [details/pytorch.md](details/pytorch.md) |
| cann/runtime（采集 + ACL 上报） | [prior/runtime.md](prior/runtime.md) | [details/runtime.md](details/runtime.md) |
| Ascend/msprof（解析） | [prior/msprof.md](prior/msprof.md) | [details/msprof.md](details/msprof.md) |
| cann/driver | [prior/driver.md](prior/driver.md) | [details/driver.md](details/driver.md) |
| cann/ge | [prior/ge.md](prior/ge.md) | [details/ge-hcomm.md](details/ge-hcomm.md) |
| cann/hcomm（HCCL 上报） | [prior/hcomm.md](prior/hcomm.md) | [details/ge-hcomm.md](details/ge-hcomm.md) |
| cann/hccl、ops-* | [prior/ops-hccl.md](prior/ops-hccl.md) | 无稳定 Report 点则不必细节 |

总流向：[prior/overview.md](prior/overview.md)
