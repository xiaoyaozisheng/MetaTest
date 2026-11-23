# 配置说明（metatest.yaml）

`metatest init` 可生成按语言预填的配置。PRD FR-01 示例风格的嵌套写法与顶层写法均支持
（`mutation` / `quality_gate` / `flaky` / `cache` / `report` / `adapter` 放在 `project:` 内或顶层皆可）。

## 最小示例

```yaml
trust: true            # init 生成即可信；手写配置可省略（见下方"安全"）
project:
  name: demo
  language: python
  build_cmd: ""
  test_cmd: "pytest -q --junitxml=report.xml"
  test_result_format: junit_xml
  source_roots: ["src"]
  test_roots: ["tests"]
  parallelism: 4
  timeout_sec: 120
  mutation:
    operators: ["relational", "boolean", "return_value", "statement_deletion"]
    incremental: true
```

## 字段总览

### project

| 字段 | 默认 | 说明 |
|------|------|------|
| `name` | `unnamed` | 项目名（缓存键与报告使用） |
| `language` | `python` | `python` / `c` / `command`（其他语言用 command 接入） |
| `build_cmd` | `""` | 构建命令；留空时 python 无需构建，c 自动探测 CMake/Make |
| `test_cmd` | — | 测试命令（必填；C 项目可用 `adapter.test_binary` 替代） |
| `test_result_format` | `junit_xml` | `junit_xml` / `exit_code` |
| `source_roots` | `["src"]` | 被变异的源码目录 |
| `test_roots` | `["tests"]` | 测试目录（质量分析范围） |
| `parallelism` | `4` | 变异体并行执行数 |
| `timeout_sec` | `120` | 单条构建/测试命令超时（秒） |
| `env` | `{}` | 传递给测试命令的环境变量 |
| `junit_path` | 自动推断 | 结果文件相对路径；默认从 test_cmd 中解析 `--junitxml=` 等 |

### mutation

| 字段 | 默认 | 说明 |
|------|------|------|
| `operators` | `all` | 算子白名单，见下表；支持 `all` |
| `exclude_operators` | `[]` | 算子黑名单 |
| `incremental` | `false` | 增量模式（也可用 CLI `--incremental` 临时开启） |
| `exclude_globs` | `[]` | 源码文件排除（fnmatch，相对项目根） |
| `include_globs` | `[]` | 源码文件包含（为空表示全部） |
| `fail_fast` | `false` | pytest 场景注入 `-x`，测试失败时尽早终止该变异体的测试运行 |
| `test_selection` | `false` | 测试关联筛选（Python/pytest）：用 coverage 动态上下文建立"行 → 测试"映射，每个变异体只运行覆盖它的测试；零覆盖变异直接判 survived 免执行。前提：测试确定性、无跨测试耦合（与增量模式同一前提） |
| `strategy` | `auto` | 变异策略：`auto`（按语言策略链自动选择）/ `ast` / `tree_sitter` / `fallback` / `llvm_ir`（需外部插件注册，Mull/muti 类）；C 语言下 `adapter.c_parser` 显式指定时视同本字段 |
| `rule_files` | `[]` | 规则化变异（universalmutator 思路）：YAML 规则文件列表（`rules[].operator/swaps`），配置后 command 接入的任意语言项目也可变异；需同时配置 source_roots 与 include_globs。格式与示例见 docs/adapters.md |

变异算子（Python / C 共享语义定义）：

| 算子 | 说明 | 别名 |
|------|------|------|
| `relational` | 关系运算符替换：> ↔ >=、< ↔ <=、== ↔ != | |
| `arithmetic` | 算术运算符替换：+ ↔ -、* ↔ / | |
| `boolean_negation` | 布尔取反：not/! 移除、True/False 翻转、&& ↔ \|\| | `boolean` |
| `return_value` | 返回值替换：return expr → None/0 | |
| `statement_deletion` | 删除语句 | |
| `boundary_value` | 边界值修改：比较中整数常量 +1 | `boundary` |
| `condition_constant` | 条件常量替换：if/三元 → True/False | `condition` |
| `none_replacement` | None/空指针替换：调用实参 → None/NULL | `none` |
| `exception_removal` | 异常删除：raise → pass、吞异常 → 再抛出（仅 Python） | `exception` |
| `loop_condition` | 循环条件修改：while → False、range 缩短（C：条件 → 0） | `loop` |

### quality_gate

| 字段 | 默认 | 说明 |
|------|------|------|
| `enabled` | `true` | 门禁开关 |
| `min_mutation_score` | `null` | 变异得分阈值（0-100），低于则退出码 1 |
| `fail_on_survived` | `false` | 存在漏测变异即失败 |
| `max_flaky` | `null` | flaky 测试数量上限 |
| `max_weak_assertions` | `null` | 弱断言测试数量上限 |

### flaky

| 字段 | 默认 | 说明 |
|------|------|------|
| `enabled` | `true` | `metatest run` 时附带 flaky 检测（额外运行 N 次测试套件） |
| `runs` | `3` | 重复运行次数（≥2） |

> flaky 检测在沙箱中运行。依赖外部状态文件的"确定性 flaky"测试，请把状态文件写到
> 沙箱外（约定环境变量 `FLAKY_STATE_FILE` 指向绝对路径）；基于随机/时间的 flaky 开箱即用。

### cache / sandbox / report

| 字段 | 默认 | 说明 |
|------|------|------|
| `cache.enabled` | `true` | 结果缓存（键含代码内容哈希，改动自动失效） |
| `cache.dir` | `.metatest` | 缓存与等价标记文件目录 |
| `sandbox.copy_exclude` | `[]` | 沙箱复制时额外排除的目录/文件 |
| `report.formats` | `[html, json, junit_xml]` | 报告格式 |
| `report.output_dir` | `.metatest/report` | 报告输出目录 |

### adapter（语言专属）

| 字段 | 适用 | 说明 |
|------|------|------|
| `build_dir` | c | CMake 构建目录（默认 `build`） |
| `test_binary` | c | 测试二进制名（跨平台调用：Windows 直接执行、POSIX 加 `./`） |
| `c_parser` | c | C 变异后端：`tree_sitter`（推荐）/ `fallback` / `auto`（默认自动：有 tree-sitter 用之，否则词法回退并显著告警）。**显式指定 `tree_sitter` 而依赖缺失时退出码 2**。每个变异体都记录生成引擎（`engine` 字段），报告含分引擎统计（`engine_scores`），词法回退的得分请在报告中单独解读 |
| `coverage_xml` | 通用 | coverage.xml 路径（默认 `coverage.xml`，存在即做覆盖率×变异得分结合） |

## CI 环境变量覆盖（PRD FR-01）

| 环境变量 | 覆盖 |
|----------|------|
| `METATEST_TEST_CMD` | test_cmd |
| `METATEST_BUILD_CMD` | build_cmd |
| `METATEST_PARALLELISM` | parallelism |
| `METATEST_TIMEOUT_SEC` | timeout_sec |
| `METATEST_OUTPUT_DIR` | report.output_dir |
| `METATEST_LANGUAGE` | language |
| `METATEST_ALLOW_COMMANDS` | `1` 时允许执行不可信配置中的命令（CI 中显式允许） |

## 安全（信任判定逻辑）

MetaTest 会执行配置中的命令。判定原则：**仓库内容无法自我授权** —— 配置文件里写
`trust: true` **不再**授予执行权（v0.1.1 起弃用；否则攻击者可随仓库提交恶意配置诱导执行）。

可信判定按顺序检查，命中其一即放行：

1. **用户级信任存储** `~/.metatest/trusted.json`（可用 `METATEST_TRUST_STORE` 环境变量覆盖位置）：
   * `metatest init` 生成配置时自动登记；
   * `metatest allow --config <path>` 显式登记；
   * 键 = 配置绝对路径，值 = **配置内容 SHA-256 指纹** —— 配置文件被改动（哪怕一行注释）
     信任立即失效，需重新 `metatest allow`；`metatest deny` 撤销；
2. `metatest run --allow-commands`：本次一次性放行；
3. `METATEST_ALLOW_COMMANDS=1`：CI 中显式允许（模板已内置）。

未命中时 `metatest run` 退出码 2 并给出指引。执行期防护：全部命令在独立沙箱目录中运行、
超时强制终止进程树、沙箱排除 `.git`/构建产物等。

## 等价变异体（人工标记）

得分的可信度受等价变异影响。把确认无害的变异标记进 `.metatest/equivalents.yaml`（从报告中复制变异 id 或位置）：

```yaml
equivalents:
  - "src/calc.py:10:relational"        # path:line:operator —— 该行该算子全部变异
  - "src/calc.py:12"                   # path:line —— 该行全部变异
  - "src/log.py:*:return_value"        # 通配
```

被标记的变异状态置为 `equivalent`，从得分分母排除。报告中的"疑似等价"提示来自内置启发式
（`__repr__`/`__str__`/`__hash__` 等方法内的返回值变异）。
