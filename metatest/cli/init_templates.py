"""metatest init 模板（PRD FR-01）。"""

PYTHON_YAML = """\
# MetaTest 配置（由 metatest init 生成，字段说明见 docs/configuration.md）
# 信任不来自本文件：metatest init 已登记到用户级存储（~/.metatest/trusted.json）
# 配置被改动后需 metatest allow 重新确认；仓库内内容无法自我授权
project:
  name: {name}
  language: python
  build_cmd: ""
  test_cmd: "python -m pytest -q"        # pytest 运行 unittest 套件亦可
  test_result_format: junit_xml          # 统一结果输入（pytest 自动注入 --junitxml）
  source_roots: ["src"]
  test_roots: ["tests"]
  parallelism: 4
  timeout_sec: 120

mutation:
  operators: all                         # 或列表: [relational, arithmetic, ...]
  exclude_operators: []
  incremental: false                     # true 时 PR 场景只评估改动相关变异
  fail_fast: false                       # 测试失败时尽早结束该变异体的测试运行

quality_gate:
  enabled: true
  min_mutation_score: null               # 例如 80.0：低于阈值退出码 1
  fail_on_survived: false                # true：存在漏测变异即失败
  max_flaky: null                        # flaky 数量上限
  max_weak_assertions: null

flaky:
  enabled: true
  runs: 3                                # 同一测试重复运行次数

cache:
  enabled: true
  dir: .metatest

report:
  formats: [html, json, junit_xml]
  output_dir: .metatest/report
"""

C_YAML = """\
# MetaTest 配置（由 metatest init 生成，字段说明见 docs/configuration.md）
project:
  name: {name}
  language: c
  # 构建方式三选一：
  #   1) 留空 + CMakeLists.txt  → 自动 cmake + ctest（--output-junit 产出 JUnit XML）
  #   2) 留空 + Makefile        → 自动 make
  #   3) 显式命令（下例直接用 gcc，无需 make/cmake）
  build_cmd: "gcc -Isrc -o calc_test.exe src/calc.c tests/calc_test.c"
  test_cmd: "calc_test.exe"
  test_result_format: exit_code          # CTest 项目可改 junit_xml
  source_roots: ["src"]
  test_roots: ["tests"]
  parallelism: 4
  timeout_sec: 120
  adapter:
    build_dir: build                     # cmake 模式构建目录
    c_parser: auto                       # tree_sitter | fallback | auto

mutation:
  operators: all
  exclude_operators: [exception_removal] # C 无异常机制，该算子不生成
  incremental: false

quality_gate:
  enabled: true
  min_mutation_score: null

report:
  formats: [html, json, junit_xml]
  output_dir: .metatest/report
"""

COMMAND_YAML = """\
# MetaTest 配置（由 metatest init 生成，字段说明见 docs/configuration.md）
# 命令级接入（PRD FR-02）：任意语言/脚本项目只需提供命令与结果格式。
project:
  name: {name}
  language: command
  build_cmd: ""
  test_cmd: "python check.py"            # 退出码 0=通过，非 0=失败
  test_result_format: exit_code          # 或 junit_xml（test_cmd 需产出 JUnit XML）
  source_roots: []
  test_roots: []
  parallelism: 1
  timeout_sec: 60

flaky:
  enabled: true
  runs: 3

report:
  formats: [html, json, junit_xml]
  output_dir: .metatest/report
"""


def template_for(language: str, name: str) -> str:
    tpl = {"python": PYTHON_YAML, "c": C_YAML, "command": COMMAND_YAML}.get(language)
    if tpl is None:
        raise ValueError(f"未知语言: {language}")
    return tpl.format(name=name)
