# 生态借鉴图谱：MetaTest × 开源项目

> MetaTest 不复制任何项目，而是在适配器协议与元测试层做集成创新（PRD 第 7 节）。
> 本文记录对相关开源项目的调研结论（2026-11 实测核实）、各自可借鉴机制，以及
> MetaTest 中对应的落点；同时诚实标注"未借鉴/未核实"的部分。

## 1. 变异测试类

### universalmutator（[agroce/universalmutator](https://github.com/agroce/universalmutator)）

**形态**：基于正则规则的多语言源码级变异（内置 C/C++/Python/Java/Swift/Rust/Solidity/JS/Go 等），
规则可由用户扩展；不做 AST 解析。

**借鉴落点**：`metatest/mutators/rule_mutator.py` —— 规则文件驱动的语言无关变异器：
* YAML 声明符号交换对（`{operator, swaps}`），掩码注释/字符串后做"独立符号"定位；
* 配置 `mutation.rule_files` + `include_globs` 后，**command 适配器接入的任意语言项目
  也能变异**（此前 command 接入只能做结果校验/质量分析，无变异能力）；
* 生成引擎记为 `rules`，与 AST 级得分分列（同词法回退的审计口径）。

**未借鉴**：其逐变异体完整重跑模型被我们的调度引擎替代；正则规则改写以"独立符号
交换"为安全子集，不做任意正则重写（降低语法错误变异率）。

### Mull（[mull-project/mull](https://github.com/mull-project/mull)）与 muti

**形态**：LLVM IR / bitcode 内存级变异（编译期注入），速度快、CI-native
（git-aware scoping、CI 注解）。

**借鉴落点**：变异**策略注册表**（`metatest/mutators/__init__.py`）：
* C 的策略链 `llvm_ir → tree_sitter → fallback`，`mutation.strategy` / CLI `--strategy`
  可显式指定，`auto` 按可用性自动选择并在报告记录选择链；
* `llvm_ir` 是**外部插件插槽**：Mull 类引擎以
  `register_mutation_strategy("c", "llvm_ir", factory)` 注册后自动进入链首
  （测试 `test_llvm_ir_plugin_slot` 锁定该契约）；
* 增量模式（git diff）对应 Mull 的 git-aware scoping；JUnit XML 对应 CI 注解的
  等价落点。

**未借鉴**：不内置 LLVM 依赖（可移植性优先，PRD 已预判）。

### mutmut / cosmic-ray（Python）

**借鉴落点**：AST 算子集与"每个变异体独立沙箱 + 并行 + 缓存"的调度形态；
缓存键含代码内容哈希的失效策略。均为自研实现的思路参照，非代码复用。

## 2. 测试质量分析类

### sixth_sense（[ydah/sixth_sense](https://github.com/ydah/sixth_sense)，Ruby gem）

**形态**：对测试套件做三轴评分 —— adequacy（覆盖率+变异得分）、redundancy（冗余）、
maintainability（test smell）。

**借鉴落点**：`metatest/core/quality.py::quality_axes` —— 语言无关的**三轴质量评分**，
进入质量报告与 HTML/JSON 输出：
* adequacy = 变异得分（有 run 数据时）；
* redundancy = 重复测试组数；
* maintainability = 弱断言（test smell）数 —— 且该维度现已扩展到 **C**（tree-sitter
  解析测试函数的断言密度/常量断言/无断言，`find_weak_assertions_c`），
  这是"语言无关综合质量分析"空白点的实质性推进（此前仅 Python AST）。

### mutant / other Ruby 工具

仅作维参参考，未借鉴具体机制。

## 3. Flaky 检测类

### flakeguard（[smartcontractkit/flakeguard](https://github.com/smartcontractkit/flakeguard)）

**形态**：CI flaky 门禁 CLI，detect（多次运行检测）/ guard（门禁）/ quarantine（隔离清单）。

**借鉴落点**：
* **隔离复测分类**（第二阶段）：对被标记的 flaky 测试单独复跑 N 次，区分
  `isolated_flaky`（单测也 flaky）/ `order_dependent`（套件内顺序/状态依赖）/
  `isolated_failing`（单独恒失败）—— `metatest flaky --isolate`；
* detect/guard 双模式分别对应 `metatest flaky` 与 `quality_gate.max_flaky` 门禁。

**未借鉴**：quarantine 清单管理（属于测试管理平台范畴，PRD 非目标）。

### flakewall

**核实结论：未能找到该名称的开源项目**（PRD 引用存疑）。flaky 维度的可复用成熟方案
实际为 FlaPy（se2p/flapy）、box/flaky、Trunk Flaky Tests 等；MetaTest 采用
JUnit XML 统一输入 + 多次运行统计的通用方案，与上述工具可互替。

## 4. 落点汇总

| 空白点（构想分析） | MetaTest 落点 | 状态 |
|---|---|---|
| 多语言变异统一入口（按语言自动选策略） | 策略注册表 + 选择链（ast/tree_sitter/fallback/rule/llvm_ir 插槽）+ `--strategy` | ✅ 已实现 |
| 语言无关变异扩展 | 规则化变异器（rule_files）使 command 接入项目可变异 | ✅ 已实现 |
| 语言无关质量分析 | C 弱断言（tree-sitter）+ 三轴质量评分 | ✅ 已实现（弱断言仅覆盖 C/Python，其余语言待补） |
| Flaky 复用 + 增强 | 内置检测 + 隔离分类（flakeguard 式） | ✅ 已实现 |
| 元测试（最大空白） | 17 个已知答案基准 + selftest + 真实缺陷库验证（docs/bugbench.md） | ✅ 已实现 |
| 平台编排 | 统一 CLI/CI + 退出码 + 策略/得分审计（engine_scores） | ✅ 已实现 |
