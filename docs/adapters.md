# 适配器协议与插件

## 适配器协议（PRD FR-02）

统一接口，所有语言适配器实现同一生命周期：

```python
class BaseAdapter:
    @classmethod
    def detect(cls, root, config=None) -> int:
        """探测项目是否适合本适配器，返回置信度 0-100（metatest init 自动探测用）。"""

    def prepare(self) -> None:
        """运行前环境校验（pytest 可用？cmake 可用？）；失败抛 AdapterError → 退出码 2。"""

    def generate_mutants(self, operators: list) -> list[MutantSpec]:
        """生成变异候选。command 适配器返回 []（命令级接入不做语法级变异）。"""

    def build(self, work_dir, timeout) -> ProcResult | None:
        """构建（如需）。每个变异体都在独立沙箱目录中重新构建。"""

    def run_tests(self, work_dir, timeout) -> TestRunResult:
        """在沙箱 work_dir 中构建并运行测试，返回结构化结果。"""

    def parse_result(self, work_dir, proc) -> TestRunResult:
        """结果判定：优先 JUnit XML（统一输入），回退退出码。"""

    def cleanup(self) -> None: ...
```

内置适配器：

| 名称 | 变异 | 结果输入 | 典型项目 |
|------|------|----------|----------|
| `python` | AST（10 算子） | pytest `--junitxml`（未配置时自动注入） | pytest / unittest 套件 |
| `c` | tree-sitter（回退：词法级） | ctest `--output-junit` / 自研 harness 退出码 | gcc / Make / CMake+CTest |
| `command` | 无（结果校验+质量分析） | 退出码或任意 JUnit XML | 任意语言/脚本 |

## 命令级接入（任意语言）

只需在 `metatest.yaml` 提供命令与结果格式，即可获得 flaky 检测、测试结果校验、报告与门禁：

```yaml
project:
  name: my_go_project
  language: command
  build_cmd: "go build ./..."
  test_cmd: "go test ./... -json | go-junit-report > report.xml"
  test_result_format: junit_xml     # 或 exit_code
```

### 规则化变异：command 接入也能变异（universalmutator 思路）

command 接入默认零变异体；配置 `mutation.rule_files` 后，任意语言项目可获得
语法层变异 —— 用 YAML 声明"独立符号交换对"，变异器在掩码（注释/字符串）后的
源码上定位并交换（生成引擎记为 `rules`，报告按引擎分列得分）：

```yaml
project:
  name: my_go_project
  language: command
  build_cmd: "go build ./..."
  test_cmd: "go test ./... -json | go-junit-report > report.xml"
  test_result_format: junit_xml
  source_roots: ["src"]                 # 被变异目录（此前可留空，规则化变异时必填）
  mutation:                             # 顶层写法亦可
    rule_files: ["rules/go.yaml"]
    include_globs: ["src/**/*.go"]      # globstar 支持（** 跨目录段）

# rules/go.yaml
# rules:
#   - operator: relational
#     swaps: [["==", "!="], ["<=", "<"], [">=", ">"]]
#   - operator: go_bool
#     swaps: [["&&", "||"], ["!", ""]]
```

要点：只做独立符号交换（不做表达式重写），注释/字符串/行注释自动屏蔽；
规则文件的 operator 名进入报告（可与内置算子名不同）。

## 变异策略注册表（按语言自动选择）

统一入口按"策略链"为语言选择最佳可用变异引擎（`mutation.strategy` / CLI `--strategy`）：

| 语言 | 策略链（优先级降序） | 说明 |
|------|---------------------|------|
| python | `ast` | 内置 AST 变异 |
| c | `llvm_ir → tree_sitter → fallback` | `auto` 自动选择；显式指定时缺依赖退出码 2 |
| 任意语言 | `rule`（配置 rule_files 时） | 规则化变异器 |

* 每个变异体记录生成引擎（`engine` 字段），报告含 `engine_scores` 分引擎统计；
* `llvm_ir` 是外部插件插槽（Mull/muti 类 IR 级引擎）：插件调用
  `register_mutation_strategy("c", "llvm_ir", factory)` 注册后自动进入链首，
  契约由测试 `test_llvm_ir_plugin_slot` 锁定；
* 选择链与跳过原因写入 results.json 的 `strategy` 字段。

## 插件机制（PRD FR-10）

三类扩展点：变异算子、语言适配器。加载方式：

1. **entry points**（包分发）：`[project.entry-points."metatest.plugins"]`
2. **本地目录**：`metatest run --plugin-dir my_plugins` 或配置

   ```yaml
   plugins:
     dirs: ["my_plugins"]
   ```

插件契约：模块提供 `register(ctx)`：

```python
# my_plugins/example_operator_plugin.py —— 由 metatest plugins template 导出
import ast
from metatest.mutators.base import Mutation

OPERATOR_NAME = "zero_constant"

def gen_zero_constant(node, ctx):
    """算子函数签名：fn(node, ctx) -> list[Mutation]"""
    if not isinstance(node, ast.Constant):
        return []
    if isinstance(node.value, bool) or not isinstance(node.value, int) or node.value != 0:
        return []
    start, end = ctx.offset(node)
    return [Mutation(start, end, "1", OPERATOR_NAME, "整数常量 0 → 1")]

def register(ctx):
    ctx.register_python_operator(OPERATOR_NAME, gen_zero_constant)
    # ctx.register_c_operator(name, fn)        # C 算子（tree-sitter 节点）
    # ctx.register_adapter(name, cls)         # 语言适配器（BaseAdapter 子类）
```

使用：`metatest run --operators zero_constant --plugin-dir my_plugins`。

验收路径（PRD 11）：复制模板 → 修改算子函数 → 通过 `--plugin-dir` 加载 → 新算子出现在
`metatest plugins list` 并参与变异。

## C 变异引擎选型说明（PRD 开放问题）

MVP 采用 **tree-sitter**（精度与可移植折中）：

- `tree_sitter` + `tree_sitter_c`：AST 级变异，区分乘法/指针解引用、精确运算符定位；
- 无依赖回退：词法级保守变异（屏蔽注释/字符串/预处理行），支持关系/算术/布尔/条件/边界/返回值/循环算子；
- 预留：`adapter.c_parser` 可切换后端；LLVM IR 级变异（Mull 类）作为后续插件接入点。

Clang AST 方案精度更高但要求用户环境安装 LLVM，未作为 MVP 默认。
