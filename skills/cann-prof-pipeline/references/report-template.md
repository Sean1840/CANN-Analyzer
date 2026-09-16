# 分析报告模板（强制）

每一份给用户的结论都必须按下面填写。缺项视为没做完。不要用 evidence pack / signals 等词对用户说话。

```text
## 分析报告

代码时间点: <repo_id> @ <commit前12位> (<ref>)，索引时间 <indexed_at>
（无命中则写：仅依据日志内嵌 file:line，基线索引未覆盖该条）

### 输入
- 数据：<ascend_pt / PROF_* / 未提供>
- 日志：<plog 路径或粘贴 / 未提供>
- pid：ascend_pt文件名 / PROF info.json / plog ；对不上则停止分析
- 现象：<用户原话或未提供；可仅口头+ret=>

### 问题
<用户现象，一句话；无现象则写从数据/日志看到的首个 ERROR 或缺口>

### 责任组件
<上报 | 采集 | 解析 | 业务环境 | 不支持> — <仓> <目录或模块>

### 证据
- 日志原文（plog 字段：LEVEL / MODULE / file:line / tid / message）
- 产物：缺/有哪个 host_start、*.done、db、csv
- 索引命中：path:line / fingerprint 或「未命中」

### 来源
- 基线 sqlite / 本地 overlay 再 index 的仓与 commit
- 若未对齐现场版本，标明「版本未对齐」

### 解决方案
- 现场可执行的下一步；能改代码时按 [version-and-fix.md](version-and-fix.md)（改法 + 是否已合入/PR + 用户包版本）
- 因缺数据中断：列出还要的 PROF/plog，先给初步结论
- 读实现才 clone；查行号只 `index --repo`

### 分析链
- 已走：<组件1> → <组件2> → …
- 停止原因：根因已落在本组件 / 下一跳不在已收集日志的组件内
```

## 分析链（必须跑完）

按 [analysis-chain.md](analysis-chain.md)：解析/采集报错后，用原始件、中间 db 或临时解析把**那一条**捞出来，再沿上报→采集→解析走。停在「xx 失败」不算完成。超出 profiling 链则转办、不套本模板全文。
