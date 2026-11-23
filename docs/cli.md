# CLI 说明

全局选项：`--verbose`（调试日志）、`--quiet`（精简输出）、`--version`。
所有命令的退出码遵循 PRD FR-09：`0` 成功 · `1` 质量门禁失败 · `2` 平台/配置错误 · `3` 自检失败。

## metatest init

```bash
metatest init [dir] [--language python|c|command] [--force]
```

在目标目录生成 `metatest.yaml`（`trust: true`）。省略 `--language` 时自动探测：
pyproject/setup.py → python；CMakeLists/Makefile/*.c → c；否则 command。

## metatest python

```bash
metatest python [--config metatest.yaml] [--project-root DIR] [--set EXE] [--clear]
```

列出候选 Python 解释器（实测 pytest 可用性），或为该项目绑定一个解释器
（用户级存储 `~/.metatest/interpreters.json`，不写入仓库配置）。
解决「PATH 上的 python 没装 pytest → 基线 0 个用例」的典型问题。

## metatest ui

```bash
metatest ui [--host 127.0.0.1] [--port N] [--no-browser] [--project DIR]
```

启动本地 Web 控制台（仅回环监听），自动打开浏览器。界面上的每次操作都等价于对应 CLI 命令，
结果与退出码语义一致。详见 [web-console.md](web-console.md)。

## metatest run（核心命令）

```bash
metatest run [--config metatest.yaml] [选项]
```

流程：加载配置 → 加载插件 → 适配器准备 → 生成变异体 →（增量筛选）→ 基线测试 →
并行执行（沙箱 + 超时 + 缓存）→ 质量分析 → 报告 → 门禁判定。

| 选项 | 说明 |
|------|------|
| `--incremental` | 增量模式：只评估改动相关变异体 |
| `--diff-ref REF` | git diff 基准（默认 `HEAD`，即未提交改动；PR 场景用 `origin/main`） |
| `--changed-files a.py,b.py` | 显式改动文件列表（无 git 场景，如制品构建） |
| `--operators op1,op2` | 算子白名单（覆盖配置） |
| `--exclude-operators op1,op2` | 算子黑名单 |
| `--parallel N` | 并行度（覆盖配置） |
| `--timeout SEC` | 单命令超时（覆盖配置） |
| `--no-cache` | 忽略并禁用结果缓存 |
| `--test-selection` | 测试关联筛选：coverage 动态上下文建立"行 → 测试"映射，每个变异体只运行覆盖它的测试；零覆盖直接判 survived（Python/pytest） |
| `--flaky` | 强制运行 flaky 检测 |
| `--no-quality` | 跳过质量分析（弱断言/重复/flaky），只做变异测试 |
| `--output-dir DIR` | 报告输出目录（覆盖配置） |
| `--formats html,json,junit_xml` | 报告格式（覆盖配置） |
| `--allow-commands` | 允许执行不可信配置中的命令 |
| `--equivalents FILE` | 等价变异标记文件（默认 `.metatest/equivalents.yaml`） |
| `--plugin-dir DIR` | 加载插件目录（可多次） |

增量筛选粒度：文件级 + 函数级。Python 通过 AST 定位改动行所在函数（函数内任一改动
→ 该函数整体相关）；C 使用改动行范围（hunk ± 3 行）。

退出码：基线测试失败 / 配置错误 / 环境缺失 → `2`；门禁未达标 → `1`；其余成功 → `0`。
基线运行存在失败或全部跳过时拒绝评估 —— "跳过不等于通过"是元测试核心原则。

## metatest selftest

```bash
metatest selftest [--list] [--case ID]... [--baseline-dir DIR] [--json PATH]
```

运行内置基准项目库（已知答案项目，数量随版本增长，清单见 docs/selftest.md），验证平台判断正确性。
任何非跳过用例失败 → 退出码 `3`。`--baseline-dir` 可指向自有基准库。

## metatest flaky

```bash
metatest flaky [--runs N] [--config ...] [--plugin-dir ...]
```

重复运行测试套件 N 次，逐用例统计不稳定率。检测到 flaky → 退出码 `1`（可直接用于 CI）。

## metatest quality

```bash
metatest quality [--flaky] [--json PATH] [--strict]
```

静态质量分析：弱断言 / 重复测试（/ flaky）。`--strict` 时发现即退出码 `1`。
覆盖率×变异得分结合在 `metatest run` 报告中展示（需 `coverage.xml`）。

## metatest report

```bash
metatest report --results .metatest/report/results.json --format html --out report.html
```

从 results.json 重新渲染报告（无需重跑变异）。

## metatest allow / deny

```bash
metatest allow --config metatest.yaml    # 显式信任（写入用户级存储，绑定内容指纹）
metatest deny --config metatest.yaml     # 撤销信任
```

信任判定与安全模型见 docs/configuration.md 安全章节；`metatest init` 已自动登记。

## metatest plugins

```bash
metatest plugins list                    # 内置适配器/算子 + 已加载插件
metatest plugins template [--dest PATH]  # 导出插件模板（新增变异算子示例）
```

## metatest ci

```bash
metatest ci github [--out .github/workflows/metatest.yml]
metatest ci gitlab [--out .gitlab-ci.yml]
```

输出官方 CI 模板（与 docs/ci.md 相同内容）。
