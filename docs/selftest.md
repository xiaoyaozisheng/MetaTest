# 元测试自检（selftest）

> "误判风险：平台自身判断错误会误导用户，元测试是必须项而非可选项。" —— PRD 第 10 节

`metatest selftest` 用**已知答案**的基准项目验证 MetaTest 自身的判断是否正确。
自检失败意味着平台不可信，退出码 `3`，CI 必须失败。

## 基准项目库

内置 17 个基准项目（`metatest/metatests/`），覆盖 PRD FR-08 的全部类型：

| case | 类型 | 已知答案 | 验证点 |
|------|------|----------|--------|
| `py_must_fail` | 必失败 | fail | 不把失败误报为通过 |
| `py_must_pass` | 必通过 | pass | 不把通过误报为失败 |
| `py_skip` | 部分跳过 | pass_with_skips | **跳过 ≠ 通过** |
| `py_all_skipped` | 全部跳过 | all_skipped | 拒绝把"什么都没测"当通过 |
| `py_timeout` | 超时 | timeout | 超时判定 + 进程终止 |
| `py_weak_assert` | 弱断言 | 3 个测试被标记 | 质量分析有效性 |
| `py_flaky` | 交替失败 | flaky=true | flaky 检测有效性 |
| `py_mutant_kill` | 变异必杀死 | 4 个变异 killed | Python 变异执行 + 判定 |
| `py_mutant_survive` | 变异必存活 | 2 个变异 survived | 漏测报告 |
| `command_must_pass` | 命令级接入 | pass | 退出码 0 → pass |
| `command_must_fail` | 命令级接入 | fail | 退出码 1 → fail |
| `c_must_pass` | C 必通过 | pass | C 适配器（缺编译器自动跳过） |
| `c_must_fail` | C 必失败 | fail | C 适配器 |
| `c_mutant_kill` | C 变异必杀死 | 2 个变异 killed | C 变异引擎 |
| `py_equivalent_manual` | 等价变异（人工标记） | equivalent + 分母排除 | 等价标记管道 |
| `py_equivalent_suspect` | 等价变异（启发式） | suspect 标记 + survived | dunder 启发式 |
| `c_lexical_guard` | 词法误伤防护 | 宏/字符串/注释区零变异、零 error | 引擎可信度 |

## 运行

```bash
metatest selftest                # 全部
metatest selftest --list         # 列出基准项目
metatest selftest --case py_flaky --case py_timeout   # 指定用例
metatest selftest --json selftest.json                # JSON 输出（CI 用）
```

每个基准项目复制到独立临时目录运行（互不污染、无残留）。环境缺失（如无 C 编译器）
的用例标记为 `skipped`，不计入通过率，透明报告。

## 编写自有基准项目

任何满足结构的项目都可加入基准库（`--baseline-dir` 指向目录）：

```
my_baseline/
├── metatest.yaml      # 项目配置
├── src/  tests/       # 项目内容
└── selftest.yaml      # 已知答案
```

`selftest.yaml` 的四种 kind：

```yaml
case_id: my_case
description: 说明
kind: test_run          # 验证测试结果分类
expect: { outcome: fail }        # pass / fail / pass_with_skips / all_skipped / timeout

kind: mutation          # 验证变异判定
expect:
  mutants:
    - { path: src/x.py, operator: relational, lineno: 10, status: killed }

kind: flaky             # 验证 flaky 检测
runs: 3
expect: { flaky: true }

kind: weak_assert       # 验证弱断言检测
expect: { tests: [test_x] }
```

## CI 用法

自检必须是 CI 中最先执行的一步（平台不可信时，后续任何结论都不可信）：

```yaml
# GitHub Actions
- run: metatest selftest        # 退出码 3 → job 失败
```

完整 CI 模板见 `metatest ci github|gitlab` 或 [docs/ci.md](ci.md)。
