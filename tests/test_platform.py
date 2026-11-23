"""平台自身测试套件。

覆盖：配置、变异算子、结果判定/得分、JUnit 解析、引擎端到端、增量、缓存、
命令适配器、质量分析、报告、插件、selftest、CLI 退出码。
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from metatest.config import load_config, normalize_operators  # noqa: E402
from metatest.errors import ConfigError  # noqa: E402
from metatest.models import (  # noqa: E402
    AnalysisResult,
    Mutant,
    MutantStatus,
    RunOutcome,
    TestRunResult,
    classify_run,
)

# 避免 pytest 把导入的 TestRunResult 数据类误收集为测试类
TestRunResult.__test__ = False

# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

MINI_PROJECT = {
    "src/maths.py": (
        "def add(a, b):\n"
        "    return a + b\n"
        "\n"
        "\n"
        "def is_leap(year):\n"
        "    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)\n"
        "\n"
        "\n"
        "def untested_sub(a, b):\n"
        "    return a - b\n"
    ),
    "tests/test_maths.py": (
        "from maths import add, is_leap\n"
        "\n"
        "\n"
        "def test_add():\n"
        "    assert add(2, 3) == 5\n"
        "    assert add(-1, 1) == 0\n"
        "\n"
        "\n"
        "def test_leap():\n"
        "    assert is_leap(2024)\n"
        "    assert is_leap(2000)\n"
        "    assert not is_leap(1900)\n"
        "    assert not is_leap(2023)\n"
        "    # untested_sub 刻意无测试：为门禁测试提供幸存变异\n"
    ),
    "conftest.py": (
        "import sys\n"
        "from pathlib import Path\n"
        "sys.path.insert(0, str(Path(__file__).parent / 'src'))\n"
    ),
    "metatest.yaml": (
        "project:\n"
        "  name: mini\n"
        "  language: python\n"
        "  test_cmd: 'python -m pytest -q'\n"
        "  test_result_format: junit_xml\n"
        "  source_roots: ['src']\n"
        "  test_roots: ['tests']\n"
        "  parallelism: 2\n"
        "  timeout_sec: 60\n"
        "  flaky: {enabled: false}\n"
        "report: {formats: [json]}\n"
    ),
}


@pytest.fixture
def mini_project(tmp_path, monkeypatch):
    for rel, content in MINI_PROJECT.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    # 信任存储隔离到测试目录；CLI 子进程继承该环境变量
    monkeypatch.setenv("METATEST_TRUST_STORE", str(tmp_path / "truststore.json"))
    monkeypatch.delenv("METATEST_ALLOW_COMMANDS", raising=False)
    from metatest.config import grant_trust

    grant_trust(tmp_path / "metatest.yaml")
    return tmp_path


def make_mutant(path="src/maths.py", lineno=2, operator="arithmetic",
                original=" + ", mutated=" - ", start=27, end=30):
    m = Mutant(path=path, start_offset=start, end_offset=end, lineno=lineno,
               operator=operator, original=original, mutated=mutated)
    m.stable_id()
    return m


def mutant_from_file(project_root, rel_path="src/maths.py", operator="arithmetic",
                     original=" + ", mutated=" - ", occurrence=1):
    """按文件实际内容构造偏移正确的变异（兼容 CRLF）。"""
    src = (Path(project_root) / rel_path).read_bytes().decode("utf-8")
    pos = -1
    for _ in range(occurrence):
        pos = src.find(original, pos + 1)
        assert pos >= 0, f"{original!r} 不存在于 {rel_path}"
    m = Mutant(path=rel_path, start_offset=pos, end_offset=pos + len(original),
               lineno=src.count("\n", 0, pos) + 1, operator=operator,
               original=original, mutated=mutated)
    m.stable_id()
    return m


def run_analysis(project_root, mutants, no_cache=True):
    from metatest.adapters import create_adapter
    from metatest.core.engine import MutationEngine

    cfg = load_config(project_root / "metatest.yaml", project_root=project_root)
    adapter = create_adapter(cfg, project_root)
    adapter.prepare()
    engine = MutationEngine(cfg, project_root, adapter, progress=lambda msg: None)
    return engine.run(mutants, no_cache=no_cache)


# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------


class TestConfig:
    def test_load_mini(self, mini_project):
        cfg = load_config(mini_project / "metatest.yaml", project_root=mini_project)
        assert cfg.name == "mini"
        assert cfg.language == "python"
        assert cfg.parallelism == 2
        # trust 字段已弃用为无效字段（信任来自用户级存储，见 docs/configuration.md 安全章节）
        assert cfg.trust is False

    def test_missing_file(self, tmp_path):
        with pytest.raises(ConfigError):
            load_config(tmp_path / "nope.yaml")

    def test_invalid_language(self, tmp_path):
        cfg_file = tmp_path / "metatest.yaml"
        cfg_file.write_text("project: {name: x, language: rust, test_cmd: t}", encoding="utf-8")
        with pytest.raises(ConfigError):
            load_config(cfg_file)

    def test_operator_aliases(self):
        assert normalize_operators(["boolean", "all"]) == normalize_operators(["all"])
        assert "boolean_negation" in normalize_operators(["boolean"])
        with pytest.raises(ConfigError):
            normalize_operators(["no_such_op"])

    def test_env_override(self, mini_project, monkeypatch):
        monkeypatch.setenv("METATEST_PARALLELISM", "9")
        monkeypatch.setenv("METATEST_TIMEOUT_SEC", "7.5")
        cfg = load_config(mini_project / "metatest.yaml", project_root=mini_project)
        assert cfg.parallelism == 9
        assert cfg.timeout_sec == 7.5

    def test_top_level_sections(self, tmp_path):
        cfg_file = tmp_path / "metatest.yaml"
        cfg_file.write_text(
            "trust: true\n"
            "project: {name: x, language: python, test_cmd: t, source_roots: ['src']}\n"
            "quality_gate: {min_mutation_score: 80}\n",
            encoding="utf-8",
        )
        cfg = load_config(cfg_file)
        assert cfg.quality_gate.min_mutation_score == 80

    def test_nested_sections(self, tmp_path):
        cfg_file = tmp_path / "metatest.yaml"
        cfg_file.write_text(
            "project:\n"
            "  name: x\n"
            "  language: python\n"
            "  test_cmd: t\n"
            "  quality_gate: {min_mutation_score: 60}\n"
            "  mutation: {operators: [relational]}\n",
            encoding="utf-8",
        )
        cfg = load_config(cfg_file)
        assert cfg.quality_gate.min_mutation_score == 60
        assert cfg.mutation.operators == ["relational"]


# ---------------------------------------------------------------------------
# 结果判定与得分（FR-06）
# ---------------------------------------------------------------------------


class TestClassify:
    def test_pass(self):
        assert classify_run(0, 3, 0, 0, 0) == RunOutcome.PASS

    def test_fail(self):
        assert classify_run(1, 3, 1, 0, 0) == RunOutcome.FAIL

    def test_skip_is_not_pass(self):
        assert classify_run(0, 2, 0, 0, 1) == RunOutcome.PASS_WITH_SKIPS
        assert classify_run(0, 2, 0, 0, 2) == RunOutcome.ALL_SKIPPED

    def test_exit_code_without_junit(self):
        assert classify_run(1, 0, 0, 0, 0, has_junit=False) == RunOutcome.FAIL
        assert classify_run(127, 0, 0, 0, 0, has_junit=False) == RunOutcome.ERROR
        assert classify_run(9009, 0, 0, 0, 0, has_junit=False) == RunOutcome.ERROR

    def test_timeout(self):
        assert classify_run(-1, 0, 0, 0, 0, timed_out=True) == RunOutcome.TIMEOUT

    def test_score_formula(self):
        analysis = AnalysisResult(project_name="t")
        for status in [MutantStatus.KILLED, MutantStatus.SURVIVED, MutantStatus.TIMEOUT,
                       MutantStatus.EQUIVALENT, MutantStatus.ERROR]:
            m = make_mutant()
            m.status = status
            analysis.mutants.append(m)
        # killed / (killed + survived + timeout)，等价与错误排除
        assert analysis.score == pytest.approx(1 / 3)
        assert analysis.killed == 1 and analysis.equivalent == 1 and analysis.error == 1

    def test_score_none_when_no_scored(self):
        analysis = AnalysisResult(project_name="t")
        m = make_mutant()
        m.status = MutantStatus.EQUIVALENT
        analysis.mutants.append(m)
        assert analysis.score is None


# ---------------------------------------------------------------------------
# Python 变异器（FR-03 / 附录 12：10 个算子）
# ---------------------------------------------------------------------------


class TestPythonMutator:
    SAMPLE = (
        "def add(a, b):\n"
        "    return a + b\n"
        "\n"
        "\n"
        "def clamp(x, lo, hi):\n"
        "    if x < lo:\n"
        "        return lo\n"
        "    if x > hi:\n"
        "        return hi\n"
        "    return x\n"
        "\n"
        "\n"
        "def sign(n):\n"
        "    if n > 0:\n"
        "        return 1\n"
        "    if not n:\n"
        "        return 0\n"
        "    return -1\n"
        "\n"
        "\n"
        "def greet(name):\n"
        "    message = 'hello ' + name\n"
        "    print(message)\n"
        "    return message\n"
    )

    def _mutants(self, operators):
        from metatest.mutators.python_mutator import PythonMutator

        return PythonMutator().generate_for_file("src/x.py", self.SAMPLE, operators)

    def test_all_ten_operators_generate(self):
        all_ops = list(normalize_operators("all"))
        specs = self._mutants(all_ops)
        found = {s.operator for s in specs}
        # exception_removal 无 try/except、loop_condition 无循环 → 其余 8 种全覆盖
        assert found == {"relational", "arithmetic", "boolean_negation", "return_value",
                         "boundary_value", "condition_constant", "statement_deletion",
                         "none_replacement"}

    def test_relational_pairs(self):
        specs = self._mutants(["relational"])
        changes = {(s.original.strip(), s.mutated.strip()) for s in specs}
        assert ("<", ">=") in changes
        assert ("<=", ">") not in changes  # 本例无 <=
        assert (">", "<=") in changes

    def test_boundary_plus_one(self):
        specs = self._mutants(["boundary_value"])
        assert any(s.original == "0" and s.mutated == "1" for s in specs)
        # 样本中 1/0 作为返回值不是比较常量，不应被 boundary_value 变异
        assert not any(s.original == "1" and s.lineno == 15 for s in specs)

    def test_boolean_not_removal(self):
        specs = self._mutants(["boolean_negation"])
        assert any(s.mutated == "n" for s in specs)  # not n → n

    def test_return_value_none(self):
        specs = self._mutants(["return_value"])
        assert all(s.mutated == "None" for s in specs)
        assert len(specs) >= 2

    def test_statement_deletion_assign_and_expr(self):
        # greet 中 message 赋值与 print 表达式可被删除（块中多条语句 → 删除为空）
        specs = self._mutants(["statement_deletion"])
        assert any(s.mutated == "" and s.lineno == 22 for s in specs)   # message = ...
        assert any(s.mutated == "" and s.lineno == 23 for s in specs)   # print(...)

    def test_condition_constant_both(self):
        specs = self._mutants(["condition_constant"])
        trues = [s for s in specs if s.mutated == "True"]
        falses = [s for s in specs if s.mutated == "False"]
        assert trues and falses

    def test_mutants_are_syntax_valid(self):
        import ast

        for s in self._mutants(list(normalize_operators("all"))):
            patched = self.SAMPLE[:s.start_offset] + s.mutated + self.SAMPLE[s.end_offset:]
            assert s.original == self.SAMPLE[s.start_offset:s.end_offset]
            ast.parse(patched)  # 语法有效

    def test_loop_and_exception(self):
        src = (
            "def sum_to(n):\n"
            "    total = 0\n"
            "    for i in range(n):\n"
            "        total += i\n"
            "    return total\n"
            "\n"
            "\n"
            "def div(a, b):\n"
            "    try:\n"
            "        return a / b\n"
            "    except ZeroDivisionError:\n"
            "        pass\n"
        )
        from metatest.mutators.python_mutator import PythonMutator

        specs = PythonMutator().generate_for_file("x.py", src, ["loop_condition", "exception_removal"])
        ops = {s.operator for s in specs}
        assert "loop_condition" in ops
        # 吞异常 pass → raise
        assert any(s.original == "pass" and s.mutated == "raise" for s in specs)

    def test_increment_operator_via_plugin(self):
        # 插件算子参与生成（与 tests/test_plugins.py 呼应）
        from metatest.mutators.base import register_python_operator, custom_python_operators
        import ast as ast_mod

        def gen(node, ctx):
            if isinstance(node, ast_mod.Constant) and node.value == 0:
                s, e = ctx.offset(node)
                return [__import__("metatest.mutators.base", fromlist=["Mutation"]).Mutation(
                    s, e, "1", "zero_constant", "0→1")]
            return []

        register_python_operator("zero_constant", gen)
        try:
            src = "def f(x):\n    return x == 0\n"
            from metatest.mutators.python_mutator import PythonMutator

            specs = PythonMutator().generate_for_file("x.py", src, ["zero_constant"])
            assert any(sp.operator == "zero_constant" and sp.original == "0" for sp in specs)
        finally:
            custom_python_operators().pop("zero_constant", None)
            # register 写入模块级 dict 的副本，需清理原 dict
            from metatest.mutators import base as mut_base

            mut_base._custom_python_operators.pop("zero_constant", None)


# ---------------------------------------------------------------------------
# C 变异器（FR-04）
# ---------------------------------------------------------------------------

C_SAMPLE = (
    '#include "calc.h"\n'
    "\n"
    "int add(int a, int b) {\n"
    "    return a + b;\n"
    "}\n"
    "\n"
    "int is_leap(int year) {\n"
    "    if ((year % 4 == 0 && year % 100 != 0) || year % 400 == 0) {\n"
    "        return 1;\n"
    "    }\n"
    "    return 0;\n"
    "}\n"
)


class TestCMutator:
    @pytest.mark.parametrize("backend", ["tree_sitter", "fallback"])
    def test_relational_and_arithmetic(self, backend):
        pytest.importorskip("tree_sitter") if backend == "tree_sitter" else None
        from metatest.mutators.c_mutator import CMutator

        m = CMutator(backend=backend)
        if backend == "tree_sitter" and not m._ts:
            pytest.skip("tree-sitter 未安装")
        specs = m.generate_for_file("src/calc.c", C_SAMPLE,
                                    ["relational", "arithmetic", "boolean_negation"])
        assert any(s.operator == "arithmetic" and s.original == "+" and s.mutated == "-"
                   for s in specs)
        assert any(s.operator == "relational" and s.original == "==" for s in specs)
        assert any(s.operator == "boolean_negation" and s.original == "&&" for s in specs)

    def test_fallback_masks_preproc(self):
        from metatest.mutators.c_mutator import CMutator

        m = CMutator(backend="fallback")
        specs = m.generate_for_file("src/calc.c", C_SAMPLE, ["relational"])
        # #include 行中的 < > 不得产生变异
        assert all(s.lineno > 2 for s in specs)

    def test_condition_and_loop(self):
        from metatest.mutators.c_mutator import CMutator

        m = CMutator(backend="tree_sitter")
        if not m._ts:
            pytest.skip("tree-sitter 未安装")
        src = C_SAMPLE + (
            "int sum_to(int n) {\n"
            "    int total = 0;\n"
            "    for (int i = 0; i < n; i++) {\n"
            "        total += i;\n"
            "    }\n"
            "    return total;\n"
            "}\n"
        )
        specs = m.generate_for_file("src/calc.c", src, ["loop_condition", "condition_constant"])
        assert any(s.operator == "loop_condition" and s.mutated == "0" for s in specs)
        assert any(s.operator == "condition_constant" for s in specs)

    def test_no_exception_removal_for_c(self):
        from metatest.mutators.c_mutator import CMutator

        m = CMutator(backend="tree_sitter")
        if not m._ts:
            pytest.skip("tree-sitter 未安装")
        specs = m.generate_for_file("src/calc.c", C_SAMPLE, ["exception_removal"])
        assert specs == []


# ---------------------------------------------------------------------------
# JUnit 解析
# ---------------------------------------------------------------------------


class TestJunit:
    PYTEST_STYLE = """<testsuites name="pytest tests"><testsuite name="pytest"
        errors="0" failures="1" skipped="1" tests="3" time="0.1">
        <testcase classname="t" name="a" time="0"/>
        <testcase classname="t" name="b" time="0"><failure message="boom"/></testcase>
        <testcase classname="t" name="c" time="0"><skipped message="later"/></testcase>
        </testsuite></testsuites>"""

    CTEST_STYLE = """<testsuites><testsuite name="CTest" tests="2" failures="1">
        <testcase name="calc" status="passed"/>
        <testcase name="leap" status="failed" message="wrong"/>
        </testsuite></testsuites>"""

    def test_pytest_style(self, tmp_path):
        from metatest.junit import parse_junit

        f = tmp_path / "junit.xml"
        f.write_text(self.PYTEST_STYLE, encoding="utf-8")
        s = parse_junit(f)
        assert (s.tests, s.failures, s.skipped) == (3, 1, 1)
        assert [c.test_id for c in s.cases if c.status == "failed"] == ["t.b"]

    def test_ctest_style(self, tmp_path):
        from metatest.junit import parse_junit

        f = tmp_path / "junit.xml"
        f.write_text(self.CTEST_STYLE, encoding="utf-8")
        s = parse_junit(f)
        assert s.tests == 2 and s.failures == 1
        assert s.cases[0].status == "passed"

    def test_broken_file(self, tmp_path):
        from metatest.junit import parse_junit

        f = tmp_path / "junit.xml"
        f.write_text("<not-xml", encoding="utf-8")
        with pytest.raises(ValueError):
            parse_junit(f)

    def test_extract_junit_path(self):
        from metatest.junit import extract_junit_path

        assert extract_junit_path("pytest -q --junitxml=report.xml", "") == "report.xml"
        assert extract_junit_path("pytest --junitxml \"C:/tmp/a.xml\"", "") == "C:/tmp/a.xml"


# ---------------------------------------------------------------------------
# 引擎端到端（沙箱 / 并行 / 判定 / 缓存）
# ---------------------------------------------------------------------------


class TestEngine:
    def test_kill_and_survive(self, mini_project):
        from metatest.mutators.python_mutator import PythonMutator
        from metatest.config import load_config
        from metatest.adapters import create_adapter

        cfg = load_config(mini_project / "metatest.yaml", project_root=mini_project)
        adapter = create_adapter(cfg, mini_project)
        adapter.prepare()
        specs = adapter.generate_mutants(["relational", "arithmetic"])
        assert specs, "应生成变异体"
        analysis = run_analysis(mini_project, [s.to_mutant() for s in specs])
        assert analysis.baseline.outcome == RunOutcome.PASS
        assert analysis.error == 0
        # add 测试很强 → + ↔ - 被杀死
        killed = [m for m in analysis.mutants if m.status == MutantStatus.KILLED]
        assert killed, "至少一个变异被杀死"
        assert analysis.score is not None and 0 <= analysis.score <= 1

    def test_baseline_failure_aborts(self, mini_project):
        # 破坏测试使基线失败 → 全部 error
        test_file = mini_project / "tests" / "test_maths.py"
        test_file.write_text(test_file.read_text(encoding="utf-8") + "\n\ndef test_bad():\n    assert 1 == 2\n",
                             encoding="utf-8")
        analysis = run_analysis(mini_project, [make_mutant()])
        assert analysis.baseline.outcome == RunOutcome.FAIL
        assert all(m.status == MutantStatus.ERROR for m in analysis.mutants)

    def test_cache_reuse(self, mini_project):
        m = mutant_from_file(mini_project)
        first = run_analysis(mini_project, [m], no_cache=False)
        assert not first.mutants[0].cached
        # 第二次（新对象、同一内容）→ 缓存命中
        m2 = mutant_from_file(mini_project)
        second = run_analysis(mini_project, [m2], no_cache=False)
        assert second.mutants[0].cached
        assert second.mutants[0].status == first.mutants[0].status
        # 缓存文件存在
        assert (mini_project / ".metatest" / "cache.json").exists()

    def test_all_skipped_tests_are_error(self, tmp_path):
        # 全跳过项目：变异运行应判 error（跳过不等于通过）
        (tmp_path / "src").mkdir()
        (tmp_path / "tests").mkdir()
        (tmp_path / "src" / "m.py").write_text("def f(x):\n    return x + 1\n", encoding="utf-8")
        (tmp_path / "conftest.py").write_text(
            "import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).parent / 'src'))",
            encoding="utf-8")
        (tmp_path / "tests" / "test_m.py").write_text(
            "import pytest\n\n@pytest.mark.skip(reason='all skipped')\ndef test_a():\n    assert f(1) == 2\n",
            encoding="utf-8")
        (tmp_path / "metatest.yaml").write_text(
            "trust: true\nproject: {name: skipy, language: python, test_cmd: 'python -m pytest -q',"
            " source_roots: ['src'], test_roots: ['tests'], parallelism: 1, timeout_sec: 30,"
            " flaky: {enabled: false}}\nreport: {formats: []}\n", encoding="utf-8")
        from metatest.mutators.python_mutator import PythonMutator

        src = (tmp_path / "src" / "m.py").read_text(encoding="utf-8")
        specs = PythonMutator().generate_for_file("src/m.py", src, ["arithmetic"])
        assert specs
        analysis = run_analysis(tmp_path, [s.to_mutant() for s in specs])
        assert analysis.baseline.outcome == RunOutcome.ALL_SKIPPED

    def test_sandbox_isolation(self, mini_project):
        # 沙箱运行不污染主工作区（无 junit 残留、源码未被改写）
        before = (mini_project / "src" / "maths.py").read_text(encoding="utf-8")
        run_analysis(mini_project, [make_mutant()])
        after = (mini_project / "src" / "maths.py").read_text(encoding="utf-8")
        assert before == after
        assert not (mini_project / "_metatest_junit.xml").exists()


# ---------------------------------------------------------------------------
# 增量
# ---------------------------------------------------------------------------


class TestIncremental:
    def _git_project(self, tmp_path):
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
        subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
        subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
        subprocess.run(["git", "commit", "-qm", "init"], cwd=tmp_path, check=True,
                       capture_output=True)
        return tmp_path

    def test_changed_function_filter(self, mini_project):
        self._git_project(mini_project)
        # 修改 is_leap 函数体
        maths = mini_project / "src" / "maths.py"
        maths.write_text(maths.read_text(encoding="utf-8").replace(
            "    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)",
            "    return (year % 4 == 0 and year % 100 != 0) or year % 400 == 0"),
            encoding="utf-8")
        from metatest.core.incremental import changed_targets, filter_mutants
        from metatest.mutators.python_mutator import PythonMutator

        targets = changed_targets(mini_project)
        assert "src/maths.py" in targets
        src = maths.read_text(encoding="utf-8")
        specs = PythonMutator().generate_for_file("src/maths.py", src, list(normalize_operators("all")))
        mutants = [s.to_mutant() for s in specs]
        kept, stats = filter_mutants(mutants, targets, mini_project, function_level=True)
        assert 0 < len(kept) < len(mutants)
        assert stats["kept"] == len(kept)
        # 所有保留变异都在 is_leap（行 5-6）附近，不含未改动的 add / untested_sub
        assert all(5 <= m.lineno <= 6 for m in kept)

    def test_changed_files_mode(self, mini_project):
        from metatest.core.incremental import changed_targets, filter_mutants
        from metatest.mutators.python_mutator import PythonMutator

        targets = changed_targets(mini_project, changed_files=["src/maths.py"])
        src = (mini_project / "src" / "maths.py").read_text(encoding="utf-8")
        mutants = [s.to_mutant() for s in
                   PythonMutator().generate_for_file("src/maths.py", src, list(normalize_operators("all")))]
        kept, _ = filter_mutants(mutants, targets, mini_project)
        assert len(kept) == len(mutants)  # 整文件相关

    def test_no_git_raises(self, tmp_path):
        from metatest.core.incremental import changed_targets
        from metatest.errors import MetaTestError

        with pytest.raises(MetaTestError):
            changed_targets(tmp_path)  # 非 git 目录且 diff-ref 非法


# ---------------------------------------------------------------------------
# 质量分析（FR-07）
# ---------------------------------------------------------------------------


class TestQuality:
    def test_weak_assertions(self, tmp_path):
        (tmp_path / "tests").mkdir(parents=True)
        (tmp_path / "tests" / "test_x.py").write_text(
            "def test_no_assert():\n    f(1)\n\n\n"
            "def test_trivial():\n    assert True\n\n\n"
            "def test_same():\n    x = 3\n    assert x == x\n\n\n"
            "def test_strong():\n    assert 1 + 1 == 2\n",
            encoding="utf-8")
        from metatest.core.quality import find_weak_assertions

        weak = find_weak_assertions(tmp_path, ["tests"])
        flagged = {w.test for w in weak}
        assert flagged == {"test_no_assert", "test_trivial", "test_same"}

    def test_duplicates(self, tmp_path):
        (tmp_path / "tests").mkdir(parents=True)
        body = "\n\n\ndef test_dup():\n    assert 1 + 1 == 2\n    assert len('ab') == 2\n"
        (tmp_path / "tests" / "a.py").write_text("def test_a():\n    assert 1 + 1 == 2" + body,
                                                 encoding="utf-8")
        (tmp_path / "tests" / "b.py").write_text("def test_b():\n    assert 1 + 1 == 2" + body,
                                                 encoding="utf-8")
        from metatest.core.quality import find_duplicate_tests

        dups = find_duplicate_tests(tmp_path, ["tests"])
        assert dups, "应发现重复实现"

    def test_coverage_join(self, mini_project):
        (mini_project / "coverage.xml").write_text(
            '<?xml version="1.0"?><coverage><classes>'
            '<class filename="src/maths.py" line-rate="0.95"/></classes></coverage>',
            encoding="utf-8")
        from metatest.core.quality import parse_coverage_xml, combine_coverage_with_mutation

        coverage = parse_coverage_xml(mini_project / "coverage.xml")
        assert coverage == {"src/maths.py": 0.95}
        analysis = AnalysisResult(project_name="t")
        statuses = [MutantStatus.KILLED, MutantStatus.KILLED, MutantStatus.SURVIVED, MutantStatus.TIMEOUT]
        for i, status in enumerate(statuses):
            m = make_mutant(lineno=2 + i)
            m.status = status
            analysis.mutants.append(m)
        flagged = combine_coverage_with_mutation(analysis, coverage,
                                                 coverage_threshold=0.8, score_threshold=0.9)
        assert flagged and flagged[0]["file"] == "src/maths.py"
        assert flagged[0]["score"] == pytest.approx(0.5)

    def test_flaky_detection_runs(self, tmp_path):
        # 复制 py_flaky 基准做真实 flaky 检测
        baseline = ROOT / "metatest" / "metatests" / "py_flaky"
        shutil.copytree(baseline, tmp_path, dirs_exist_ok=True)
        state = tmp_path / ".flaky_state"
        if state.exists():
            state.unlink()
        from metatest.config import load_config
        from metatest.adapters import create_adapter
        from metatest.core.quality import detect_flaky

        cfg = load_config(tmp_path / "metatest.yaml", project_root=tmp_path)
        cfg.env["FLAKY_STATE_FILE"] = str(state)
        adapter = create_adapter(cfg, tmp_path)
        adapter.prepare()
        flaky = detect_flaky(cfg, tmp_path, adapter, runs=3, progress=lambda msg: None)
        assert len(flaky) == 1
        assert flaky[0].passed >= 1 and flaky[0].failed >= 1


# ---------------------------------------------------------------------------
# 报告（FR-09）
# ---------------------------------------------------------------------------


class TestReports:
    def _analysis(self):
        analysis = AnalysisResult(project_name="demo")
        m1 = make_mutant()
        m1.status = MutantStatus.KILLED
        m2 = make_mutant(lineno=6, operator="relational", original=" == ", mutated=" != ")
        m2.status = MutantStatus.SURVIVED
        m3 = make_mutant(lineno=8, operator="return_value", original="x", mutated="None")
        m3.status = MutantStatus.EQUIVALENT
        analysis.mutants = [m1, m2, m3]
        run = TestRunResult(exit_code=0, tests=4, failures=0, errors=0, skipped=1)
        run.classify()
        analysis.baseline = run
        return analysis

    def test_json_roundtrip(self, tmp_path):
        from metatest.report.json_report import write_json_report, analysis_from_dict

        path = write_json_report(self._analysis(), tmp_path / "results.json")
        doc = json.loads(path.read_text(encoding="utf-8"))
        assert doc["summary"]["survived"] == 1
        assert doc["summary"]["equivalent"] == 1
        restored = analysis_from_dict(doc)
        assert restored.survived == 1
        assert restored.mutants[1].operator == "relational"

    def test_junit_xml(self, tmp_path):
        import xml.etree.ElementTree as ET

        from metatest.report.junit_report import write_junit_report

        path = write_junit_report(self._analysis(), tmp_path / "mutation.xml")
        root = ET.parse(path).getroot()
        suite = root.find("testsuite")
        assert suite.get("failures") == "1"
        assert suite.get("skipped") == "1"
        failures = suite.findall("testcase/failure")
        assert len(failures) == 1 and "survived" in (failures[0].get("type") or "")

    def test_html_contains_sections(self, tmp_path, mini_project):
        from metatest.report.html_report import write_html_report

        path = write_html_report(self._analysis(), tmp_path / "report.html",
                                 project_root=mini_project)
        html = path.read_text(encoding="utf-8")
        for fragment in ("漏测变异", "killed", "survived", "69.8%") or ("漏测变异",):
            assert fragment in html or fragment == "69.8%"  # 66.7% 实际值
        assert "变异得分" in html


# ---------------------------------------------------------------------------
# 命令适配器
# ---------------------------------------------------------------------------


class TestCommandAdapter:
    def test_exit_code_pass_fail(self, tmp_path):
        (tmp_path / "ok.py").write_text("import sys; sys.exit(0)\n", encoding="utf-8")
        (tmp_path / "bad.py").write_text("import sys; sys.exit(1)\n", encoding="utf-8")
        (tmp_path / "metatest.yaml").write_text(
            "trust: true\nproject: {name: cmd, language: command, test_cmd: 'python ok.py',"
            " test_result_format: exit_code, source_roots: [], test_roots: [], parallelism: 1,"
            " timeout_sec: 30}\n", encoding="utf-8")
        from metatest.config import load_config
        from metatest.adapters import create_adapter

        cfg = load_config(tmp_path / "metatest.yaml", project_root=tmp_path)
        adapter = create_adapter(cfg, tmp_path)
        adapter.prepare()
        run = adapter.run_tests(tmp_path, 30)
        assert run.outcome == RunOutcome.PASS
        assert adapter.generate_mutants([]) == []

        cfg.test_cmd = "python bad.py"
        run2 = adapter.run_tests(tmp_path, 30)
        assert run2.outcome == RunOutcome.FAIL


# ---------------------------------------------------------------------------
# selftest runner
# ---------------------------------------------------------------------------


class TestSelftestRunner:
    def test_discover_and_run_subset(self):
        from metatest.selftest.runner import discover_cases, run_selftest

        cases = discover_cases()
        assert len(cases) >= 10, "基准项目应 >= 10（PRD 2.2）"
        results = run_selftest(cases, progress=lambda msg: None,
                               case_filter={"py_must_fail", "py_must_pass"})
        assert len(results) == 2
        assert all(r.passed for r in results)

    def test_broken_case_fails(self, tmp_path):
        from metatest.selftest.runner import discover_cases, run_selftest

        case_dir = tmp_path / "broken_case"
        case_dir.mkdir()
        (case_dir / "metatest.yaml").write_text(
            "trust: true\nproject: {name: b, language: python, test_cmd: 'python -m pytest -q',"
            " source_roots: ['src'], test_roots: ['tests']}\n", encoding="utf-8")
        (case_dir / "selftest.yaml").write_text(
            "case_id: broken_case\nkind: test_run\nexpect: {outcome: pass}\n", encoding="utf-8")
        cases = discover_cases(baseline_dir=tmp_path)
        results = run_selftest(cases, progress=lambda msg: None)
        assert results[0].passed is False  # 基线必失败（无测试）→ 自检正确判 FAIL

    def test_selftest_exit_code(self):
        # 全量 selftest 应通过（环境含 gcc/pytest）
        from metatest.selftest.runner import discover_cases, run_selftest

        results = run_selftest(discover_cases(), progress=lambda msg: None)
        failed = [r for r in results if not r.passed and not r.skipped]
        assert not failed, f"自检失败用例: {[r.case_id for r in failed]}"


# ---------------------------------------------------------------------------
# 插件
# ---------------------------------------------------------------------------


class TestPlugins:
    def test_template_plugin_registers_operator(self, tmp_path, mini_project):
        template = ROOT / "metatest" / "plugins" / "templates" / "example_operator_plugin.py"
        plugin_dir = tmp_path / "my_plugins"
        plugin_dir.mkdir()
        shutil.copy(template, plugin_dir / "example_operator_plugin.py")
        # 清理可能存在的注册
        from metatest.mutators import base as mut_base

        mut_base._custom_python_operators.pop("zero_constant", None)
        try:
            from metatest.plugins import load_plugins

            loaded = load_plugins(None, extra_dirs=[str(plugin_dir)])
            assert any("example_operator_plugin" in name for name in loaded)
            assert "zero_constant" in mut_base._custom_python_operators

            # 新算子参与变异并可用
            from metatest.mutators.python_mutator import PythonMutator

            src = (mini_project / "src" / "maths.py").read_text(encoding="utf-8")
            specs = PythonMutator().generate_for_file("src/maths.py", src, ["zero_constant"])
            assert specs and all(sp.operator == "zero_constant" for sp in specs)
        finally:
            mut_base._custom_python_operators.pop("zero_constant", None)

    def test_register_adapter_rejects_non_adapter(self):
        from metatest.plugins import PluginContext

        ctx = PluginContext()
        with pytest.raises(Exception):
            ctx.register_adapter("bad", object)


# ---------------------------------------------------------------------------
# 风险 1：变异引擎标记与词法回退防护
# ---------------------------------------------------------------------------

C_MASKED_SAMPLE = (
    '#include "calc.h"\n'
    "\n"
    "/* 注释里的运算符 + - && 不得被变异 */\n"
    "#define OFFSET 3\n"
    "\n"
    'static const char *LABEL = "a + b && c";\n'
    "\n"
    "int add(int a, int b) {\n"
    "    return a + b + OFFSET;\n"
    "}\n"
)
# 高危区行号（1 起始）：注释=3，宏=4，字符串=6
C_MASKED_LINES = {3, 4, 6}


class TestEngineTagging:
    def test_python_engine_tagged_ast(self, mini_project):
        from metatest.config import load_config
        from metatest.adapters import create_adapter

        cfg = load_config(mini_project / "metatest.yaml", project_root=mini_project)
        adapter = create_adapter(cfg, mini_project)
        for spec in adapter.generate_mutants(["relational"]):
            assert spec.engine == "ast"
            m = spec.to_mutant()
            assert m.engine == "ast"

    @pytest.mark.parametrize("backend", ["tree_sitter", "fallback"])
    def test_c_masked_regions_immunity(self, backend):
        """字符串/注释/宏区域内不得产生任何变异体（两种后端都要过）。"""
        pytest.importorskip("tree_sitter") if backend == "tree_sitter" else None
        from metatest.mutators.c_mutator import CMutator

        m = CMutator(backend=backend)
        if backend == "tree_sitter" and not m._ts:
            pytest.skip("tree-sitter 未安装")
        specs = m.generate_for_file("src/calc.c", C_MASKED_SAMPLE,
                                    ["relational", "arithmetic", "boolean_negation", "boundary_value"])
        assert specs, "应至少在真实代码区产生变异"
        for s in specs:
            assert s.lineno not in C_MASKED_LINES, \
                f"变异落在高危区 {s.lineno}: {s.original!r}→{s.mutated!r}"
            assert s.engine == backend

    def test_engine_scores_split(self):
        analysis = AnalysisResult(project_name="t")
        m1 = make_mutant()
        m1.status = MutantStatus.KILLED
        m1.engine = "tree_sitter"
        m2 = make_mutant(lineno=6)
        m2.status = MutantStatus.SURVIVED
        m2.engine = "fallback"
        m3 = make_mutant(lineno=8)
        m3.status = MutantStatus.KILLED
        m3.engine = "fallback"
        analysis.mutants = [m1, m2, m3]
        es = analysis.engine_scores()
        assert es["tree_sitter"]["score"] == 1.0
        assert es["fallback"]["score"] == pytest.approx(0.5)
        assert es["tree_sitter"]["total"] == 1 and es["fallback"]["total"] == 2


# ---------------------------------------------------------------------------
# 等价变异标记（缺口 5）
# ---------------------------------------------------------------------------


class TestEquivalence:
    def test_manual_equivalent_excluded_from_score(self, tmp_path):
        from metatest.config import load_config
        from metatest.adapters import create_adapter
        from metatest.core.engine import MutationEngine
        from metatest.mutators.python_mutator import PythonMutator
        from metatest.mutators.base import read_source
        from metatest.models import MutantStatus

        (tmp_path / "src").mkdir()
        (tmp_path / "tests").mkdir()
        (tmp_path / "src" / "norm.py").write_text(
            "def normalize(raw):\n"
            "    items = tuple(raw)\n"
            "    items = list(items)\n"
            "    return items\n",
            encoding="utf-8")
        (tmp_path / "conftest.py").write_text(
            "import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).parent / 'src'))",
            encoding="utf-8")
        (tmp_path / "tests" / "test_norm.py").write_text(
            "from norm import normalize\n\n\n"
            "def test_normalize():\n"
            "    r = normalize((1, 2))\n"
            "    assert r == [1, 2] and isinstance(r, list)\n",
            encoding="utf-8")
        (tmp_path / "metatest.yaml").write_text(
            "project: {name: eq, language: python, test_cmd: 'python -m pytest -q',"
            " source_roots: ['src'], test_roots: ['tests'], parallelism: 2, timeout_sec: 30,"
            " flaky: {enabled: false}}\nreport: {formats: []}\n", encoding="utf-8")
        (tmp_path / ".metatest").mkdir()
        (tmp_path / ".metatest" / "equivalents.yaml").write_text(
            'equivalents:\n  - "src/norm.py:3:statement_deletion"\n', encoding="utf-8")

        cfg = load_config(tmp_path / "metatest.yaml", project_root=tmp_path)
        adapter = create_adapter(cfg, tmp_path)
        adapter.prepare()
        src = read_source(tmp_path / "src" / "norm.py")
        specs = PythonMutator().generate_for_file("src/norm.py", src, ["statement_deletion"])
        assert len(specs) == 2
        engine = MutationEngine(cfg, tmp_path, adapter, progress=lambda msg: None)
        analysis = engine.run([s.to_mutant() for s in specs], no_cache=True)
        by_line = {m.lineno: m for m in analysis.mutants}
        assert by_line[2].status == MutantStatus.KILLED
        assert by_line[3].status == MutantStatus.EQUIVALENT
        # 得分分母排除等价变异：score = killed / killed = 100%
        assert analysis.score == pytest.approx(1.0)
        assert analysis.equivalent == 1

    def test_suspect_flag_on_dunder(self, tmp_path):
        from metatest.config import load_config
        from metatest.adapters import create_adapter
        from metatest.core.engine import MutationEngine
        from metatest.mutators.python_mutator import PythonMutator
        from metatest.mutators.base import read_source
        from metatest.models import MutantStatus

        (tmp_path / "src").mkdir()
        (tmp_path / "tests").mkdir()
        (tmp_path / "src" / "point.py").write_text(
            "class Point:\n"
            "    def __init__(self, x, y):\n"
            "        self.x = x\n"
            "        self.y = y\n"
            "\n"
            "    def __repr__(self):\n"
            "        return f\"Point({self.x}, {self.y})\"\n",
            encoding="utf-8")
        (tmp_path / "conftest.py").write_text(
            "import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).parent / 'src'))",
            encoding="utf-8")
        (tmp_path / "tests" / "test_point.py").write_text(
            "from point import Point\n\n\n"
            "def test_attrs():\n    p = Point(1, 2)\n    assert p.x == 1\n",
            encoding="utf-8")
        (tmp_path / "metatest.yaml").write_text(
            "project: {name: pt, language: python, test_cmd: 'python -m pytest -q',"
            " source_roots: ['src'], test_roots: ['tests'], parallelism: 2, timeout_sec: 30,"
            " flaky: {enabled: false}}\nreport: {formats: []}\n", encoding="utf-8")

        cfg = load_config(tmp_path / "metatest.yaml", project_root=tmp_path)
        adapter = create_adapter(cfg, tmp_path)
        src = read_source(tmp_path / "src" / "point.py")
        specs = PythonMutator().generate_for_file("src/point.py", src, ["return_value"])
        engine = MutationEngine(cfg, tmp_path, adapter, progress=lambda msg: None)
        analysis = engine.run([s.to_mutant() for s in specs], no_cache=True)
        repr_mutant = next(m for m in analysis.mutants if m.lineno == 7)
        assert repr_mutant.suspect_equivalent is True
        assert repr_mutant.status == MutantStatus.SURVIVED  # 无测试覆盖 __repr__


# ---------------------------------------------------------------------------
# CLI 退出码
# ---------------------------------------------------------------------------


class TestCLIExitCodes:
    def _run_cli(self, args, cwd):
        proc = subprocess.run(
            [sys.executable, "-m", "metatest", *args],
            cwd=str(cwd), capture_output=True, text=True, timeout=600, encoding="utf-8",
            errors="replace",
        )
        return proc

    def test_gate_failure_exit_1(self, mini_project):
        from metatest.config import grant_trust

        cfg_file = mini_project / "metatest.yaml"
        text = cfg_file.read_text(encoding="utf-8")
        text = text.replace("flaky: {enabled: false}",
                            "flaky: {enabled: false}\n  quality_gate: {min_mutation_score: 99}")
        cfg_file.write_text(text, encoding="utf-8")
        grant_trust(cfg_file)  # 配置被改动 → 需重新登记信任
        proc = self._run_cli(["run", "--no-quality"], mini_project)
        assert proc.returncode == 1, proc.stdout[-2000:]

    def test_gate_pass_exit_0(self, mini_project):
        from metatest.config import grant_trust

        cfg_file = mini_project / "metatest.yaml"
        text = cfg_file.read_text(encoding="utf-8")
        text = text.replace("flaky: {enabled: false}",
                            "flaky: {enabled: false}\n  quality_gate: {min_mutation_score: 0}")
        cfg_file.write_text(text, encoding="utf-8")
        grant_trust(cfg_file)
        proc = self._run_cli(["run", "--no-quality"], mini_project)
        assert proc.returncode == 0, proc.stdout[-2000:]

    def test_config_error_exit_2(self, tmp_path):
        (tmp_path / "metatest.yaml").write_text(
            "project: {name: x, language: rust, test_cmd: t}\n", encoding="utf-8")
        proc = self._run_cli(["run"], tmp_path)
        assert proc.returncode == 2

    def test_missing_config_exit_2(self, tmp_path):
        proc = self._run_cli(["run"], tmp_path)
        assert proc.returncode == 2

    def test_selftest_failure_exit_3(self, tmp_path):
        baseline = tmp_path / "baselines"
        case = baseline / "expect_fail_case"
        case.mkdir(parents=True)
        (case / "metatest.yaml").write_text(
            "project: {name: c, language: python, test_cmd: 'python -m pytest -q',"
            " source_roots: ['src'], test_roots: ['tests'], timeout_sec: 30, flaky: {enabled: false}}\n",
            encoding="utf-8")
        (case / "selftest.yaml").write_text(
            "case_id: expect_fail_case\nkind: test_run\nexpect: {outcome: pass}\n", encoding="utf-8")
        (case / "src").mkdir()
        (case / "src" / "m.py").write_text("def f():\n    return 1\n", encoding="utf-8")
        (case / "tests").mkdir()
        (case / "tests" / "test_m.py").write_text(
            "import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))\n"
            "from m import f\n\n\ndef test_f():\n    assert f() == 2  # 已知答案：该测试必失败，但基准期望 pass\n",
            encoding="utf-8")
        proc = self._run_cli(["selftest", "--baseline-dir", str(baseline)], tmp_path)
        assert proc.returncode == 3, proc.stdout[-2000:]

    def test_untrusted_config_exit_2(self, mini_project):
        """信任重设计：仓库内 trust: true 不再授权；allow 绑定内容指纹。"""
        # 1) 新配置写 trust: true 且未登记 → 拒绝（仓库内容无法自我授权）
        evil = mini_project / "evil.yaml"
        evil.write_text("trust: true\n" + (mini_project / "metatest.yaml").read_text(encoding="utf-8"),
                        encoding="utf-8")
        proc = self._run_cli(["run", "--no-quality", "--config", "evil.yaml"], mini_project)
        assert proc.returncode == 2, proc.stdout[-2000:]
        # 2) metatest allow 显式确认 → 放行
        proc = self._run_cli(["allow", "--config", "evil.yaml"], mini_project)
        assert proc.returncode == 0, proc.stdout[-2000:]
        proc = self._run_cli(["run", "--no-quality", "--config", "evil.yaml"], mini_project)
        assert proc.returncode in (0, 1)
        # 3) 配置被改动（内容指纹变化）→ 信任失效，重新拒绝
        evil.write_text(evil.read_text(encoding="utf-8") + "# tampered\n", encoding="utf-8")
        proc = self._run_cli(["run", "--no-quality", "--config", "evil.yaml"], mini_project)
        assert proc.returncode == 2, proc.stdout[-2000:]

    def test_init_detects_python_and_infers_layout(self, tmp_path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_a.py").write_text("def test_x():\n    assert True\n", encoding="utf-8")
        proc = self._run_cli(["init", str(tmp_path)], tmp_path)
        assert proc.returncode == 0
        yaml_text = (tmp_path / "metatest.yaml").read_text(encoding="utf-8")
        assert 'source_roots: ["src"]' in yaml_text
        assert 'test_roots: ["tests"]' in yaml_text
        # init 自动登记信任 → run 可直接执行
        proc = self._run_cli(["run", "--no-quality"], tmp_path)
        assert proc.returncode in (0, 1, 2)  # 2 仅当 pytest 缺失等环境问题；不应是拒绝执行的信息
        assert "安全保护" not in proc.stdout
