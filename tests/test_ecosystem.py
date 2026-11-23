"""生态借鉴机制的测试：规则化变异器、策略链、C 质量分析、flaky 隔离分类、三轴评分。"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests.test_platform import mini_project  # noqa: E402,F401


class TestRuleMutator:
    SAMPLE = (
        "// comment with == and >=\n"
        "let diff = a == b;\n"
        "let flag = a && b;\n"
        'let s = "x == y";\n'
        "let neg = !ok;\n"
    )
    RULES = [
        {"operator": "relational", "swaps": [["==", "!="], ["&&", "||"], ["!", ""], ["<", "<="]]},
    ]

    def _specs(self, source, rules=None):
        from metatest.mutators.rule_mutator import RuleMutator

        return RuleMutator(rules or self.RULES).generate_for_file("src/main.go", source, [])

    def test_swaps_and_masking(self):
        specs = self._specs(self.SAMPLE)
        changes = {(s.lineno, s.original, s.mutated) for s in specs}
        # 第 2 行 a == b → a != b
        assert (2, "==", "!=") in changes
        # 第 3 行 && → ||
        assert (3, "&&", "||") in changes
        # 字符串内 "x == y" 与注释内 == 不得被变异
        assert not any(ln == 1 for ln, _o, _m in changes)
        assert not any(ln == 4 for ln, _o, _m in changes)
        assert all(s.engine == "rules" for s in specs)

    def test_no_longer_token_collision(self):
        # ==== 中间 == 不得变异；>= 的 > 不得单独变异
        src = "let a = b == c == d;\nlet x = y >= z;\n"
        specs = self._specs(src)
        assert all(s.original in ("==", "&&") for s in specs if s.operator == "relational")
        assert not any(s.original == ">" for s in specs)  # >= 内的 > 被保护

    def test_load_rule_files(self, tmp_path):
        from metatest.mutators.rule_mutator import load_rule_files
        from metatest.errors import MutationError

        f = tmp_path / "rules.yaml"
        f.write_text(
            "rules:\n"
            "  - operator: relational\n"
            "    swaps: [['==', '!=']]\n"
            "  - operator: go_bool\n"
            "    swaps: [['&&', '||']]\n", encoding="utf-8")
        rules = load_rule_files([f])
        assert len(rules) == 2
        assert rules[0]["operator"] == "relational"
        with pytest.raises(MutationError):
            load_rule_files([tmp_path / "missing.yaml"])

    def test_command_adapter_with_rules(self, tmp_path):
        """command 适配器 + 规则文件 → 任意语言获得变异能力（universalmutator 思路）。"""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.go").write_text(
            "package main\n\nfunc Leq(a int, b int) bool {\n\treturn a <= b\n}\n",
            encoding="utf-8")
        (tmp_path / "rules.yaml").write_text(
            "rules:\n  - operator: relational\n    swaps: [['<=', '<']]\n", encoding="utf-8")
        (tmp_path / "metatest.yaml").write_text(
            "project: {name: gogo, language: command, test_cmd: 'python -c \"exit(0)\"',"
            " test_result_format: exit_code, source_roots: ['src'], test_roots: [],"
            " parallelism: 1, timeout_sec: 30}\n"
            "mutation: {rule_files: ['rules.yaml'], include_globs: ['src/**/*.go']}\n"
            "report: {formats: []}\n", encoding="utf-8")
        from metatest.config import load_config
        from metatest.adapters import create_adapter
        from metatest.mutators.base import read_source

        cfg = load_config(tmp_path / "metatest.yaml", project_root=tmp_path)
        adapter = create_adapter(cfg, tmp_path)
        adapter.prepare()
        specs = adapter.generate_mutants([])
        assert specs and specs[0].engine == "rules"
        assert specs[0].original == "<=" and specs[0].mutated == "<"
        # 变异体可应用（文本片段匹配）
        src = read_source(tmp_path / "src" / "app.go")
        patched = src[:specs[0].start_offset] + specs[0].mutated + src[specs[0].end_offset:]
        assert patched.count("<=") == 0


class TestStrategyChain:
    def test_python_resolves_ast(self, mini_project):
        from metatest.config import load_config
        from metatest.mutators import resolve_mutator

        cfg = load_config(mini_project / "metatest.yaml", project_root=mini_project)
        mutator, info = resolve_mutator(cfg, mini_project)
        assert info["strategy"] == "ast"
        assert mutator.language == "python"

    def test_c_chain_prefers_tree_sitter(self, tmp_path):
        pytest.importorskip("tree_sitter")
        from metatest.config import load_config
        from metatest.mutators import resolve_mutator

        (tmp_path / "metatest.yaml").write_text(
            "project: {name: c, language: c, build_cmd: 'gcc -o t t.c', test_cmd: './t.exe',"
            " source_roots: ['src']}\n", encoding="utf-8")
        cfg = load_config(tmp_path / "metatest.yaml", project_root=tmp_path)
        mutator, info = resolve_mutator(cfg, tmp_path)
        assert info["strategy"] == "tree_sitter"

    def test_c_strict_tree_sitter_missing_raises(self, tmp_path, monkeypatch):
        from metatest.config import load_config
        from metatest.mutators import resolve_mutator
        from metatest.errors import MutationError

        (tmp_path / "metatest.yaml").write_text(
            "project: {name: c, language: c, build_cmd: 'gcc', test_cmd: './t',"
            " source_roots: ['src'], adapter: {c_parser: tree_sitter}}\n", encoding="utf-8")
        cfg = load_config(tmp_path / "metatest.yaml", project_root=tmp_path)
        monkeypatch.setitem(sys.modules, "tree_sitter", None)
        # 构造依赖缺失环境（临时屏蔽 import）
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *a, **k):
            if name.startswith("tree_sitter"):
                raise ImportError("blocked for test")
            return real_import(name, *a, **k)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        with pytest.raises(MutationError):
            resolve_mutator(cfg, tmp_path)

    def test_llvm_ir_plugin_slot(self, tmp_path):
        """Mull/muti 类 IR 级引擎的插件插槽：注册后进入链首。"""
        from metatest.mutators import register_mutation_strategy, resolve_mutator, _custom_mutators
        from metatest.config import load_config

        (tmp_path / "metatest.yaml").write_text(
            "project: {name: c, language: c, build_cmd: 'gcc', test_cmd: './t',"
            " source_roots: ['src']}\n", encoding="utf-8")
        cfg = load_config(tmp_path / "metatest.yaml", project_root=tmp_path)

        class FakeIRMutator:
            language = "c"
            file_exts = (".c",)

            def generate_for_file(self, rel, source, operators):
                return []

        try:
            register_mutation_strategy("c", "llvm_ir", FakeIRMutator)
            mutator, info = resolve_mutator(cfg, tmp_path)
            assert info["strategy"] == "llvm_ir"
            assert isinstance(mutator, FakeIRMutator)
        finally:
            _custom_mutators.pop(("c", "llvm_ir"), None)
        # 未注册时回退链继续
        mutator, info = resolve_mutator(cfg, tmp_path)
        assert info["strategy"] != "llvm_ir"

    def test_unknown_strategy_raises(self, tmp_path):
        from metatest.config import load_config
        from metatest.mutators import resolve_mutator
        from metatest.errors import MutationError

        (tmp_path / "metatest.yaml").write_text(
            "project: {name: c, language: c, build_cmd: 'gcc', test_cmd: './t',"
            " source_roots: ['src']}\nmutation: {strategy: bogus}\n", encoding="utf-8")
        cfg = load_config(tmp_path / "metatest.yaml", project_root=tmp_path)
        with pytest.raises(MutationError):
            resolve_mutator(cfg, tmp_path)


class TestCQuality:
    def test_c_weak_assertions_ast(self, tmp_path):
        pytest.importorskip("tree_sitter")
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "calc_test.c").write_text(
            '#include <stdio.h>\n'
            'static int failures = 0;\n'
            '#define CHECK(c) do { if (!(c)) failures++; } while (0)\n'
            '\n'
            'void test_strong(void) {\n'
            '    CHECK(add(1, 2) == 3);\n'
            '}\n'
            '\n'
            'void test_no_assert(void) {\n'
            '    int x = add(1, 2);\n'
            '    (void)x;\n'
            '}\n'
            '\n'
            'void test_trivial(void) {\n'
            '    CHECK(1);\n'
            '}\n',
            encoding="utf-8")
        from metatest.core.quality import find_weak_assertions_c

        weak = find_weak_assertions_c(tmp_path, ["tests"])
        flagged = {w.test: w.reason for w in weak}
        assert flagged.get("test_strong") is None
        assert flagged.get("test_no_assert") == "no_assertion"
        assert flagged.get("test_trivial") == "trivial_assert"

    def test_quality_axes(self):
        from metatest.core.quality import quality_axes
        from metatest.models import AnalysisResult, QualityReport

        q = QualityReport()
        q.duplicate_tests = [("a.py", "t1", "b.py", "t1")]
        q.weak_assertions = [type("W", (), {"file": "a", "test": "t", "lineno": 1, "reason": "x"})()]
        analysis = AnalysisResult(project_name="t")
        analysis.mutants = []
        axes = quality_axes(None, q)
        assert axes["redundancy"] == 1 and axes["maintainability"] == 1
        assert axes["adequacy"] is None


class TestFlakyIsolation:
    def test_isolated_flaky_classification(self, tmp_path):
        """py_flaky 基准（交替失败）：单独复跑仍不稳定 → isolated_flaky。"""
        import shutil

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
        flaky = detect_flaky(cfg, tmp_path, adapter, runs=3, progress=lambda msg: None,
                             isolate=True)
        assert len(flaky) == 1
        assert flaky[0].mode == "isolated_flaky"

    def test_order_dependent_classification(self, tmp_path):
        """只在套件中 flaky、单独运行恒过的测试 → order_dependent。"""
        (tmp_path / "src").mkdir()
        (tmp_path / "tests").mkdir()
        # 套件内：test_a 污染模块状态使 test_b 失败；单独跑 test_b 恒过
        (tmp_path / "src" / "counter.py").write_text("value = 0\n", encoding="utf-8")
        (tmp_path / "conftest.py").write_text(
            "import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).parent / 'src'))",
            encoding="utf-8")
        (tmp_path / "tests" / "test_pair.py").write_text(
            "import counter\n\n\n"
            "def test_a_sets_state():\n    counter.value = 99\n\n\n"
            "def test_b_fails_in_suite():\n    assert counter.value == 0\n",
            encoding="utf-8")
        (tmp_path / "metatest.yaml").write_text(
            "project: {name: od, language: python, test_cmd: 'python -m pytest -q',"
            " source_roots: ['src'], test_roots: ['tests'], parallelism: 1, timeout_sec: 30,"
            " flaky: {enabled: false}}\nreport: {formats: []}\n", encoding="utf-8")
        from metatest.config import load_config
        from metatest.adapters import create_adapter
        from metatest.core.quality import detect_flaky

        cfg = load_config(tmp_path / "metatest.yaml", project_root=tmp_path)
        adapter = create_adapter(cfg, tmp_path)
        adapter.prepare()
        # 套件内 test_b 恒失败（不是 flaky）→ 用 --runs 的历史混合构造：
        # 直接构造场景：test_b 单独恒过，套件内恒败 → 不满足 flaky 定义。
        # 因此这里验证"单独复跑恒过 → order_dependent"分类分支本身。
        from metatest.core.quality import _classify_isolation
        from metatest.models import FlakyTest

        fake = FlakyTest(test_id="tests.test_pair.test_b_fails_in_suite", runs=2,
                         passed=1, failed=1, unstable_rate=0.5, is_flaky=True)
        _classify_isolation(cfg, tmp_path, adapter, [fake], runs=2,
                            progress=lambda msg: None)
        assert fake.mode == "order_dependent"
