# 方案、合入检查、包版本

先按 [analysis-chain.md](analysis-chain.md) 把报错那条数据找到。定位到可改的代码问题后必须做完这三步。

1. **改法**：仓、文件、补什么（注册表/容错/采样）。根因在上报就改上报仓，不要只改解析白名单。
2. **查当前仓**：`git log -S` / blame 是否已合入。已合入则写日期、commit、GitCode `owner/repo!id` 链接。
3. **对齐用户包**：用 dump 时间、路径里的 CANN 版本、plog 模块版本，和修复合入日比较。
   - dump **早于**修复 → 方案是升级到含该 PR 的包，在新仓重复改是浪费。
   - dump **晚于**修复仍复现 → 该包可能没合入，或不是同一问题。
   - 日志/中间 db 和当前代码对不上 → **先问用户这份数据是什么包、什么时间编的**，再决定改代码还是升级。

有效案例：缺 type 名追到 Runtime Memset → [type-1071-memset.md](cann-prof-pipeline/references/cases/type-1071-memset.md)。
