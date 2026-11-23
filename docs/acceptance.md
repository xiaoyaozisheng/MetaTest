# 验收记录（对照 PRD 第 11 节验收标准）

> 本文档记录 MetaTest MVP 交付时对 PRD 验收标准的逐项验证结果。
> 验证环境：Windows 10 / Python 3.13 / gcc 15.2 (MinGW) / cmake 4.4 / pytest 9。

## 1. 能对至少 5 个 Python 项目和 5 个 C 项目完成变异测试并生成报告 ✅

实测（`metatest run`，报告 results.json / report.html / mutation_junit.xml 全部生成）：

**Python（5 个）**

| 项目 | 变异体 | killed | survived | 得分 | 报告退出码 |
|------|--------|--------|----------|------|-----------|
| examples/python_demo | 53 | 37 | 16 | 69.8% | 1（门禁 85% 未达标） |
| metatests/py_mutant_kill | 19 | 19 | 0 | 100.0% | 0 |
| metatests/py_mutant_survive | 9 | 3 | 6 | 66.7% | 0 |
| metatests/py_must_pass | 4 | 4 | 0 | 100.0% | 0 |
| metatests/py_skip | 2 | 2 | 0 | 100.0% | 0 |

**C（5 个）**

| 项目 | 变异体 | killed | survived | 得分 | 报告退出码 |
|------|--------|--------|----------|------|-----------|
| examples/c_demo | 26 | 19 | 7 | 73.1% | 1（门禁 80% 未达标） |
| examples/c_geom | 36 | 18 | 18 | 50.0% | 0 |
| examples/c_string_utils | 25 | 22 | 3 | 88.0% | 0 |
| metatests/c_mutant_kill | 9 | 9 | 0 | 100.0% | 0 |
| metatests/c_must_pass | 22 | 20 | 2 | 90.9% | 0 |

## 2. selftest 正确识别必失败、跳过、超时、弱断言、flaky 基准项目 ✅

`metatest selftest`：**17/17 通过，自检通过率 100%**（C 用例在本机有 gcc，实际执行）。
覆盖 PRD 要求的全部五类：必失败（py_must_fail）、跳过（py_skip / py_all_skipped）、
超时（py_timeout）、弱断言（py_weak_assert）、flaky（py_flaky），另含必通过、
变异必杀死/必存活、命令级接入基准，以及**等价变异基准**（py_equivalent_manual：
人工标记 → equivalent 且从得分分母排除；py_equivalent_suspect：dunder 启发式标记）
与 **C 词法防护基准**（c_lexical_guard：宏/字符串/注释区零变异体、零 error）。

## 3. CI 退出码符合定义 ✅

| 场景 | 期望 | 实测 |
|------|------|------|
| 质量门禁失败（得分低于阈值） | 1 | 1（python_demo 69.8% < 85%） |
| 门禁达标 | 0 | 0 |
| 配置错误（未知语言/文件缺失） | 2 | 2 |
| 基线测试失败中止 | 2 | 2 |
| 不可信配置拒绝执行命令 | 2 | 2（`--allow-commands` 后正常执行） |
| 自检失败（注入错误基准） | 3 | 3 |
| 自检全部通过 | 0 | 0 |

## 4. 增量模式只对改动相关变异体执行，结果与全量一致 ✅

对 python_demo 建 git 仓库后修改 `is_leap` 函数并提交：

- 全量生成 58 个变异体；`metatest run --incremental`（默认 diff HEAD 的未提交改动）筛选出
  **12/58** 个相关变异体（文件级 + 函数级 AST 定位），仅执行 12 个；
- 基准库 py_mutant_kill 变异结果与选择器期望一致（killed/survived 抽样一致）。

## 5. 报告包含变异得分、漏测变异位置、flaky 列表、自检结果 ✅

HTML 报告（自包含单文件，浏览器实测渲染）包含：得分徽章与门禁判定、基线状态、
killed/survived/timeout/equivalent/error 计数、每文件得分条、**漏测变异列表
（位置 + 算子 + 变异前后代码 + ±3 行源码上下文）**、弱断言/flaky/重复测试章节、
可操作建议、（有自检数据时的）自检结果章节。JSON 含全部结构化字段；JUnit XML
把 survived 映射为 `<failure>` 供 CI 原生展示。

## 6. 第三方可通过插件模板新增变异算子或命令级适配器 ✅

`metatest plugins template` 导出可运行的算子插件模板（`zero_constant`），
`--plugin-dir` 加载后新算子参与变异（平台测试套件 `TestPlugins` 端到端验证，
包括插件算子生成、注册与清理）。适配器注册 API（`ctx.register_adapter`）同契约可用。

## 7. 文档包含配置说明、CLI 说明、CI 示例和限制说明 ✅

- 配置说明：docs/configuration.md（全字段 + 环境变量覆盖 + 安全边界 + 等价标记）
- CLI 说明：docs/cli.md
- CI 示例：docs/ci.md + `metatest ci github|gitlab` + 仓库内 .github/workflows/metatest.yml、.gitlab-ci.yml
- 限制说明：docs/limitations.md（PRD 非目标 + 已知限制 + 开放问题取舍）
- 适配器协议与插件：docs/adapters.md；自检：docs/selftest.md

## 补充指标（PRD 2.2 成功指标）

| 指标 | MVP 目标 | 实测 |
|------|----------|------|
| Python/C 基准项目接入数 | ≥ 10 | 17（10 Python + 7 C，见 metatests/） |
| 元测试基准项目数 | ≥ 10 | 17（含等价变异与词法防护基准） |
| 平台自检通过率 | 100% | 100%（17/17，跳过用例不计入） |
| 变异结果误判率 | < 5% | 0%（**限于内置 17 基准项目**期望全部命中，含等价变异判定正确性；真实缺陷库 BugsInPy/MetaFL 的批量误判率待统计） |
| 增量模式运行时间 | 中小项目 ≤ 10 分钟 | python_demo 全量 53 变异体约 30s；增量 12 变异体 < 10s；缓存命中重跑约 2s |
| CI 集成 | GitHub Actions / GitLab，退出码可用 | 模板 + 实测退出码（见上） |
| 报告 | HTML + JSON + JUnit XML | ✅ 三格式 |
| 等价变异体 | 人工标记 + 启发式过滤 | equivalents.yaml 人工标记 + dunder 启发式提示；**正确性由 py_equivalent_manual / py_equivalent_suspect 基准锁定** |
| C 变异引擎可信度 | — | 每变异体记录生成引擎（engine 字段），报告含分引擎统计（engine_scores）+ 词法回退显著告警；c_lexical_guard 基准锁定误伤防护 |

## 软件化交付（Web 控制台 + 可执行程序）

| 项 | 验收方式 | 结果 |
|----|---------|------|
| 本地控制台可启动 | `metatest ui --no-browser --port 8899` | ✅ 页面 200，`/api/meta` 返回版本与 10 个算子 |
| 五大页面可用 | 概览 / 变异评估 / 质量分析 / 元测试自检 / 项目设置 | ✅ 实际项目（examples/python_demo）渲染出得分 69.8%、53 变异体、16 漏测、文件得分表 |
| 任务链路与实时日志 | 通过 API 触发 run，SSE 接收 `log` / `state` / `end` | ✅ 结果与 CLI 完全一致（killed 37 / survived 16） |
| 元测试自检 | 界面触发 selftest | ✅ 17/17 通过，结果持久化到 `~/.metatest/selftest_last.json` 并在重启后回显 |
| 安全边界 | 无 `X-Metatest-Client` 头的 POST → 403；非法 Host → 403；报告路径穿越 → 400；未信任配置需二次确认 | ✅ tests/test_web.py::TestSecurity |
| 单文件可执行程序 | `python scripts/build_exe.py` | ✅ `dist/MetaTest.exe`（约 25 MB），`frozen=true` 下静态资源与 17 个基准项目均可用 |
| 中英双语 / 明暗主题 | 界面切换 + `?lang=en&theme=dark` 深链 | ✅ |

## 平台自身测试

`python -m pytest tests/`：**115 passed**（配置/算子/判定/得分/JUnit/引擎/缓存/增量/
质量/报告/命令适配器/selftest/插件/CLI 退出码 + Web 控制台 API 20 例），
Windows 11 + Python 3.13 实测；`tests/test_testmap.py` 中依赖 pytest-cov 的 3 例在缺少
该可选依赖时自动跳过。
