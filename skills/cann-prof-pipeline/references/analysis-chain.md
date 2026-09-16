# 沿业务链追到数据

**先核对 pid。** 同时有 ascend_pt / PROF / plog 时，必须先确认是同一进程，对不上就停，告诉用户数据和日志不是一套，不要继续往下分析。

| 来源 | pid 在哪 |
|---|---|
| ascend_pt | 目录名 `..._{pid}_{时间}_ascend_pt`。用户改过名则无法从名字判断，**默认用户给的文件是一套** |
| PROF | `host/info.json` 与 `device_*/info.json*` 的 `pid`（少有人改） |
| plog | `[LEVEL] MODULE(pid,prog):时间 ...` |

`collect` / `evidence` 的 `pid_bind`：`related=false` 即 mismatch。多份 PROF 是多进程时，plog 的 pid 集合与 info.json 有交集即可。

只有口头现象、没有文件：先按模块+错误码给方向，然后要 plog/PROF。没有材料就不要沿 dump 链往下编。

只要还没到「无法定位」，就必须按先验流向继续往下问，不要停在「解析报了 xx」「采集失败」这类句子。

流向：上报发出 → 采集落盘（host/data、device_x/data）→ 解析读原始或中间 db → 交付件。

**解析报错：** 先问有没有这份数据。有则把**报错对应的那一条**从数据里找出来（现成 sqlite；没有就按先验临时解析切片、dic 文本、小脚本）。找到 type/id/时间/模块后，再判断是上报漏了、采集没写全、还是解析算错。

**采集报缺/坏：** 对照 host_start、`*.done`、对应切片是否存在、是否为空或条数不够。有切片则打开看内容，不要只看文件名。

**手段：** 中间 db、原始 slice、type_info/hash 文本、必要时临时 parser。目的是拿到报错那条内容，不是换一种方式复述日志。

**才能停：** 现有文件无法重建该条，且用户也补不了；或下一跳不在已收集仓（profiling 无关则转办，不出完整报告）。

找到可改点之后走 [version-and-fix.md](version-and-fix.md)。

范例（解析报缺 type → 从 dic+ApiData 捞到 Runtime Memset）：[type-1071-memset.md](cases/type-1071-memset.md)。
