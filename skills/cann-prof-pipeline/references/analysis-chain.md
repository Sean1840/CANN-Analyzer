# 沿业务链追到数据

**先核对 pid。** 同时有 ascend_pt / PROF / plog 时，必须先确认是同一进程，对不上就停，告诉用户数据和日志不是一套，不要继续往下分析。

| 来源 | pid 在哪 |
|---|---|
| ascend_pt | 目录名 `..._{pid}_{时间}_ascend_pt`。用户改过名则无法从名字判断，**默认用户给的文件是一套** |
| PROF | `host/info.json` 与 `device_*/info.json*` 的 `pid`（少有人改） |
| plog | `[LEVEL] MODULE(pid,prog):时间 ...` |

`collect` / `evidence` 的 `pid_bind`：`related=false` 即 mismatch。多份 PROF 是多进程时，plog 的 pid 集合与 info.json 有交集即可。

只有口头现象、没有文件：先按模块+错误码给方向，然后要 plog/PROF。没有材料就不要沿 dump 链往下编。

只要还没到「无法定位」，就按下面往下走，不要停在「解析报了 xx」「采集失败」「csv 不对」这类句子。

## 交付件字段问题（主路径）

用户说字段不对、和预期/正常导出有差异、缺列、值异常时，**从外往里比**，不要先猜仓。

```text
交付件（csv / timeline json / msprof_*.db / ASCEND_PROFILER_OUTPUT）
    │  字段是否符合预期、用户描述、正常导出
    ▼
中间 db（解析后的 sqlite：host/device sqlite，或统一 DB）
    │  没有则临时跑解析脚本/parser，把中间 db 或可读的原始表拿到手
    │  中间 db 对、交付件错  → 导出（assembler / viewer / export 配置）
    │  中间 db 已错          → 不是导出，往里看
    ▼
原始 db / 原始切片（仅当「中间」和「原始」不是同一份，中间有计算或拼接）
    │  两份一样           → 问题在更上游（采集/上报），不要在 calculate 里找
    │  原始对、中间错     → 解析组合：建树、关联、gear、calculator
    │  原始已错           → 继续上游
    ▼
采集 host/data  vs  device_*/data
    │  落在 host 切片 → host 上报组件（ACL / GE / hcomm / runtime）
    │  落在 device 切片 → device 通道（drv / AICPU / TS）
    ▼
对应业务代码（RegType、Report*、drv 通道、parser_item）
```

`all_file.complete` 是 Python 解析结束标记，不是采集件，现行路径也可以不写。

对照正常导出时：同一开关、同一芯片档、同一条命令（timeline / summary / db），只比出问题的那张表/那些列。

## C 解析 vs Python 解析

现场经常 **C / Python 混跑**（例如 C dump sqlite、Python 再 export，或反过来）。分析时：

- **不要编 C、不要跑 WrapRunPipeline / llt 当取数手段。** C 要编译，不适合在分析动作里做。
- **取数以 Python 读原始为主：** slice、dic、已有 sqlite。需要补中间表时，用 Python parser 把原始落到可读 db/表，**少跑 `mscalculate` / gear / viewer**。计算层会改行、过滤、拼接，拿它当「原始数据」会把导出/计算问题和上游搅在一起。
- **算字段、过滤、关联时对照两套实现：** Python（gear / calculator / viewer）和 C（processor / assembler）。用来对齐「这一列怎么来的」、做筛选条件、核对阈值（如 MIN_RECORD_NUM）。两套不一致时单独记一条 **C/Python 差异**（同一输入、不同过滤或拼接），不要混成采集问题。
- 现成交付件若来自 C 导出，仍用上面「交付件 → 中间 db → 原始」比；缺 db 时用 Python 从原始补表，再拿 C 代码当逻辑说明书。

## 采集报缺文件

对照 host_start、采集侧 `*.done`（如 `host_start.log.done`）、对应切片是否存在、是否为空或条数不够。有切片则打开看内容，不要只看文件名。原始目录都没有，再进 collect，不要从交付件空直接跳到采集。

## 手段

现成 sqlite、统一 DB、原始 slice、type_info/hash 文本、必要时临时 parser。目的是拿到**出问题的那一列/那一行**在每一层的样子，不是换一种方式复述日志。

## 才能停

现有文件无法重建该条，且用户也补不了；或下一跳不在已收集仓（profiling 无关则转办，不出完整报告）。

找到可改点之后走 [version-and-fix.md](version-and-fix.md)。

范例（解析报缺 type → 从 dic+ApiData 捞到 Runtime Memset）：[type-1071-memset.md](cases/type-1071-memset.md)。
