# cann/driver 细节（可能变更）

芯片宏、通道号对不上现场包时更新本页。

**host-move 注册**（`src/ascend_hal/dmc/prof/prof_interface.c`）

仅 `#ifdef CFG_SOC_PLATFORM_CLOUD_V4` 时，对 `CHANNEL_AICPU` / `CUS_AICPU` / `ADPROF`（host 再加 STARS_SOC、FFTS）返回可 host sample。其它 SOC **直接 false**。

`prof_user_sample_pre_start` 里 `is_support_host_move = true`（phase1）；phase2 用 `support_host_sample`。

runtime 平台映射（可能变）：CLOUD_V4 ↔ `DavidV121Platform`；CLOUD_V3 ↔ `DavidPlatform`。

**与口头「david 自搬、v121 走驱动」相反时：** 以 **本文件 + 现场 CANN 包编译宏** 为准，更新本页，不要改先验「由驱动在 start 选择通道或自搬」。
