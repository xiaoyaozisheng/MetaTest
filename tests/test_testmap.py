"""测试关联筛选（testmap）与零覆盖快判的测试。"""

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests.test_platform import MINI_PROJECT  # noqa: E402

# 测试关联筛选依赖 pytest-cov（可选依赖）：未安装时相关用例跳过而非失败
requires_cov = pytest.mark.skipif(
    importlib.util.find_spec("pytest_cov") is None,
    reason="需要 pytest-cov（pip install pytest-cov）才能采集测试级覆盖",
)


@pytest.fixture
def mini_project(tmp_path):
    for rel, content in MINI_PROJECT.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return tmp_path


class TestTestMap:
    @requires_cov
    def test_build_map_line_accuracy(self, mini_project):
        from metatest.config import load_config
        from metatest.core.testmap import build_test_map

        cfg = load_config(mini_project / "metatest.yaml", project_root=mini_project)
        tm = build_test_map(mini_project, cfg)
        assert tm.test_count >= 2
        # add 的 return 行（第 2 行）只被 test_add 覆盖
        cov_add = tm.covering("src/maths.py", 2)
        assert cov_add and all("test_add" in t for t in cov_add)
        # is_leap 的 return 行（第 6 行）只被 test_leap 覆盖
        cov_leap = tm.covering("src/maths.py", 6)
        assert cov_leap and all("test_leap" in t for t in cov_leap)
        # untested_sub 的 return 行（第 10 行）零覆盖
        assert tm.covering("src/maths.py", 10) == []
        assert tm.covering_lines("src/maths.py")

    def test_requires_pytest(self, mini_project):
        from metatest.config import load_config
        from metatest.core.testmap import build_test_map
        from metatest.errors import MetaTestError

        cfg = load_config(mini_project / "metatest.yaml", project_root=mini_project)
        cfg.test_cmd = "python -m unittest discover tests"
        with pytest.raises(MetaTestError):
            build_test_map(mini_project, cfg)


class TestSelectionEngine:
    def _run(self, project_root, selection, rel_path="src/maths.py", operators=("arithmetic",)):
        from metatest.config import load_config
        from metatest.adapters import create_adapter
        from metatest.core.engine import MutationEngine
        from metatest.mutators.python_mutator import PythonMutator
        from metatest.mutators.base import read_source

        cfg = load_config(project_root / "metatest.yaml", project_root=project_root)
        cfg.mutation.test_selection = selection
        adapter = create_adapter(cfg, project_root)
        adapter.prepare()
        src = read_source(project_root / rel_path)
        specs = PythonMutator().generate_for_file(rel_path, src, list(operators))
        engine = MutationEngine(cfg, project_root, adapter, progress=lambda msg: None)
        return engine.run([s.to_mutant() for s in specs], no_cache=True)

    @requires_cov
    def test_selection_consistent_with_full(self, mini_project):
        """筛选模式与全量模式的变异得分必须一致。"""
        full = self._run(mini_project, selection=False)
        sel = self._run(mini_project, selection=True)
        assert sel.test_selection is not None
        assert sel.score == pytest.approx(full.score)
        statuses_full = sorted(m.status.value for m in full.mutants)
        statuses_sel = sorted(m.status.value for m in sel.mutants)
        assert statuses_sel == statuses_full

    @requires_cov
    def test_zero_covered_survives_without_run(self, tmp_path):
        # untested_sub 无测试覆盖：其变异应被零覆盖快判为 survived，且不执行测试
        (tmp_path / "src").mkdir()
        (tmp_path / "tests").mkdir()
        (tmp_path / "src" / "m.py").write_text(
            "def used(a):\n    return a + 1\n\n\ndef unused(a):\n    return a * 2\n",
            encoding="utf-8")
        (tmp_path / "conftest.py").write_text(
            "import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).parent / 'src'))",
            encoding="utf-8")
        (tmp_path / "tests" / "test_m.py").write_text(
            "from m import used\n\n\ndef test_used():\n    assert used(1) == 2\n",
            encoding="utf-8")
        (tmp_path / "metatest.yaml").write_text(
            "trust: true\nproject: {name: zc, language: python, test_cmd: 'python -m pytest -q',"
            " source_roots: ['src'], test_roots: ['tests'], parallelism: 1, timeout_sec: 30,"
            " flaky: {enabled: false}}\nreport: {formats: []}\n", encoding="utf-8")
        from metatest.models import MutantStatus

        results = self._run(tmp_path, selection=True, rel_path="src/m.py")
        for m in results.mutants:
            if m.lineno >= 6:  # unused 函数区域
                assert m.status == MutantStatus.SURVIVED
                assert m.covered_by == 0
                assert m.duration_sec == 0.0, "零覆盖变异不应执行测试"

    def test_selection_requires_pytest_cmd(self, mini_project):
        from metatest.config import load_config
        from metatest.errors import MetaTestError
        from metatest.adapters import create_adapter
        from metatest.core.engine import MutationEngine
        from metatest.mutators.python_mutator import PythonMutator
        from metatest.mutators.base import read_source

        cfg = load_config(mini_project / "metatest.yaml", project_root=mini_project)
        cfg.mutation.test_selection = True
        cfg.test_cmd = 'python -c "exit(0)"'  # 非 pytest 命令（基线可通过）
        adapter = create_adapter(cfg, mini_project)
        src = read_source(mini_project / "src" / "maths.py")
        specs = PythonMutator().generate_for_file("src/maths.py", src, ["arithmetic"])
        assert specs
        engine = MutationEngine(cfg, mini_project, adapter, progress=lambda msg: None)
        with pytest.raises(MetaTestError):
            engine.run([s.to_mutant() for s in specs], no_cache=True)
