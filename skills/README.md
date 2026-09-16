# Skills

Profiling 故障入口是 **cann-prof-pipeline**。locate / triage 是底座。

| Skill | 角色 |
|---|---|
| [cann-prof-pipeline](cann-prof-pipeline/SKILL.md) | 分流：上报 / 采集 / 解析 / 业务环境 |
| [cann-prof-parse](cann-prof-parse/SKILL.md) | 解析产物（timeline / csv / db） |
| [cann-prof-collect](cann-prof-collect/SKILL.md) | 采集落盘、原始 PROF |
| [cann-log-locate](cann-log-locate/SKILL.md) | 一行日志 → path:line |
| [cann-log-triage](cann-log-triage/SKILL.md) | 盘点日志，打 evidence |
| [cann-analyze-eval](cann-analyze-eval/SKILL.md) | 评测，不用于现场 |
| [msprof-diagnose](msprof-diagnose/SKILL.md) | 废弃，转 pipeline |

共享文档在 `cann-prof-pipeline/references/`。安装与 CLI 见仓根 README。
