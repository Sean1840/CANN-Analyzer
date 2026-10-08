# CANN-Analyze

本仓覆盖 CANN / msprof / torch_npu profiler 的**全部分析能力**：命令行收集材料、对日志行号；skills 做分流和诊断（上报 / 采集 / 解析）。入口是 **cann-prof-pipeline**。

`cann_analyze` 只摆材料和行号，不下「根因」结论；根因由本仓 skills 按链路追数据后写出。用户说「分析这份 PROF / ascend_pt / plog」时走 pipeline，不要一上来就 parse 或 collect。交付件字段不对：先比交付件和正常导出，再中间 db，有拼接再比原始 db，原始仍错再按 host/device 上到组件。取数用 Python 读原始，不编 C；C/Python 计算逻辑只做对照和筛选。

## Skills

| Skill | 做什么 | 何时用 |
|---|---|---|
| `cann-prof-pipeline` | 看 PROF / `*_ascend_pt` / plog（或口头 drv `ret=`），把问题分到上报、采集、解析或业务环境 | 「分析这份数据」「timeline 空」「报了 EK/EE」`/cann-prof-pipeline` |
| `cann-prof-parse` | host 建树、device parse、任务关联、export、`mindstudio_profiler_output` | pipeline 判定解析，或 csv/timeline/db 结果不对 |
| `cann-prof-collect` | aclprof 启停、PROF host/device 落盘、ChannelReader | pipeline 判定采集，或原始件缺失 |
| `cann-log-locate` | 一行 slog/plog 对到源码 path:line（含 INFO/DEBUG） | 「这行日志对应哪」`/cann-log-locate` |
| `cann-log-triage` | 盘点日志和 PROF 目录，打 evidence 包，不断言根因 | 「先看看有哪些 log」`/cann-log-triage` |
| `cann-analyze-eval` | 跑 golden 用例和 rubric | 评测 locate 有效性，不用于现场诊断 |
| `msprof-diagnose` | 已废弃，立刻转 `cann-prof-pipeline` | 旧入口兼容 |

pipeline 判定解析后必须进 parse，判定采集后必须进 collect。locate / triage 是底座，不是分析入口。

共享文档在 `skills/cann-prof-pipeline/references/`（分析链、报告模板、profiling 先验/细节、msprof DB 表关联、timeline 连线）。parse / collect 通过相对路径引用，npx 时请把 cann 技能一起装。

## 安装

```bash
npx skills add Sean1840/CANN-Analyzer --list
npx skills add Sean1840/CANN-Analyzer -g -y --all
```

npx 拷贝各 skill 目录。`cann-prof-pipeline` 带 `scripts/`（CLI + catalogs + 开箱 `sites.sqlite`）。其它 cann skill 依赖 pipeline 的 `references/`，请一起装。

仓内也可：

```bat
set PYTHONPATH=tools
python -m cann_analyze skills-install --target grok
```

Grok 可以把本仓加进 `~/.grok/config.toml` 的 `[skills].paths`（建议 ignore `data/`、`.grok/`）。

## CLI

开发改 `tools/cann_analyze`。`skills/cann-prof-pipeline/scripts/` 是 npx 副本，发版时与 `tools/`、`catalogs/` 对齐。

```bat
set PYTHONPATH=tools
python -m cann_analyze status
python -m cann_analyze collect <path>
python -m cann_analyze evidence <path> -o evidence.json
python -m cann_analyze locate --line "<plog 一行>"
```

或 `scripts\cann-analyze.cmd status`。

- `collect` 盘点文件，不拷 device 二进制。
- `evidence` = collect + parse + locate。
- `locate` 读 `catalogs/baseline/sites.sqlite`，**查询时不 clone**。miss 再用已有 clone：`index --repo <id> --source <用户确认的路径>`。
- 6 位错误码走 `catalogs/cann_error_codes.json`。

## 本地配置

源码 clone 路径写在 `~/.cann-analyze/config.json` 的 `repo_paths`，或本仓 `catalogs/repos.local.json`（已 gitignore）。**第一次缺了先问用户再写**，不要猜盘符。

```json
{
  "schema": "cann-analyze.config.v1",
  "repo_paths": {
    "ascend/msprof": "/path/to/msprof",
    "cann/runtime": "/path/to/runtime"
  }
}
```

示例见 `catalogs/repos.local.json.example`。

## 布局

```text
tools/cann_analyze/     CLI（开发改这里）
catalogs/               仓表、错误码、日志宏、打分策略、开箱 sqlite
skills/                 Agent skills
  cann-prof-pipeline/   入口 + references + npx 用 scripts（由 tools/ 与 catalogs/ 同步生成）
  cann-prof-parse/
  cann-prof-collect/
  cann-log-locate/
  cann-log-triage/
  cann-analyze-eval/
docs/                   profiling 先验/细节（与 pipeline references/docs 同步）
  testing-and-gates.md  测试与质量门禁取舍
  locator-standards.md  定位量化标准与实测基线
eval/                   评测用例 + 标定数据
data/                   本地索引/镜像，不入库
```

## 测试与同步

```bat
python -m pytest tests -q                          :: 离线，秒级
python scripts/sync_skills_payload.py --check      :: 副本漂移检查（--write 重建）
python -m eval.run_eval                            :: 定位/解析指标
pwsh -File tools\rebuild_baseline.ps1              :: 重建随包索引（临时浅克隆，跑完自清）
```

`skills/cann-prof-pipeline/scripts/` 是 `tools/` 与 `catalogs/` 的副本，**只由
`scripts/sync_skills_payload.py` 生成**；`tests/test_payload_sync.py` 会在漂移时直接失败。
取舍见 [docs/testing-and-gates.md](docs/testing-and-gates.md)，量化标准与基线重建见
[docs/locator-standards.md](docs/locator-standards.md)。

评测：仓根 `PYTHONPATH=tools python eval/run_eval.py`。

## 索引点位的函数名（func）怎么看

索引里每条点位都带一个 `func`（该日志调用所在的函数），它决定 agent 拿到命中后能有多少上下文。
抽取器是轻量的括号/花括号配平扫描（纯 stdlib，不依赖编译器前端），**认不出来时留空，不猜**——
控制流关键字（`if/for/while/switch/catch/try`）永远不会被写成函数名。

看当前覆盖率：

```bat
python -m cann_analyze coverage        :: totals.func_coverage + per_repo 明细
```

单测用 `tests/fixtures_extract/` 下的 18 个片段（12 个 C++ / 6 个 Python）做**表驱动**校验：
构造函数初始化列表、模板与尾置返回、多行参数、`noexcept/override`、lambda、析构与运算符重载、
CRLF、截断文件；Python 侧 async def、装饰器/classmethod、嵌套函数、lambda 体、一行 def、制表符缩进。
每个片段的每个调用点都有 `@expect-func:` 标记，测试同时比对标记和显式期望表，
并断言"不应为空的地方不为空"。

真实规模：随包基线（`catalogs/baseline/sites.sqlite`，8 个 baseline 仓）共 38364 个点位，
其中 C++ 37211、Python 1153，`func_coverage = 0.9811`；入口仓 `ascend/msprof` 2724 个点位
（C++ 1805）、`func_coverage = 0.997`。改动前 `ascend/msprof` 只有 912 个纯 Python 点位、
C++ 为 0，且函数名几乎全空。

索引是构建产物，改了宏表或抽取器要重生成：

```bat
python -m cann_analyze index --baseline        :: 需要本机有各 baseline 仓的 clone
pwsh -File tools\rebuild_baseline.ps1          :: 自动浅克隆到 %TEMP%、重建、清理
```

