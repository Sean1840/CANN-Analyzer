# CANN 错误码（先验）

屏显/plog 6 位码：`E|W|I` + 模块 + 4 位数字。码表来自官网「错误码参考」页面（CANN 9.2.0-beta.2 保存稿），完整条目在 `catalogs/cann_error_codes.json`（343 条，含 title）。

Profiling 常用：EK0001 参数、EK0002 调用顺序、EK0003 配置、EK0004/0005 不支持、EK0201 主机内存、EK9999 内部终止。

模块字母见 json 的 `module`。后 4 位 ≥9000 为内部错误。`ret=数字` 仍只表示采集 MsprofErrorCode，与本表无关。
