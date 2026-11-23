"""全项目测试中发现的问题的回归锁定。"""

import json
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


class TestPluginOperatorWhitelist:
    """回归：插件算子曾无法通过算子白名单（normalize_operators 只认内置算子）。"""

    def test_strict_accepts_registered_custom_operator(self):
        from metatest.config import normalize_operators
        from metatest.mutators import base as mut_base

        def dummy(node, ctx):
            return []

        mut_base.register_python_operator("probe_reg_op", dummy)
        try:
            assert normalize_operators(["probe_reg_op"]) == ["probe_reg_op"]
        finally:
            mut_base._custom_python_operators.pop("probe_reg_op", None)

    def test_strict_still_rejects_unknown(self):
        from metatest.config import normalize_operators
        from metatest.errors import ConfigError

        with pytest.raises(ConfigError):
            normalize_operators(["definitely_not_an_op"])

    def test_config_load_keeps_plugin_ops_lenient(self, tmp_path):
        """配置文件可写插件算子名（插件在配置加载之后载入）。"""
        from metatest.config import load_config

        (tmp_path / "metatest.yaml").write_text(
            "project: {name: x, language: python, test_cmd: t, source_roots: ['src']}\n"
            "mutation: {operators: [probe_cfg_op, relational]}\n", encoding="utf-8")
        cfg = load_config(tmp_path / "metatest.yaml")
        assert cfg.mutation.operators == ["probe_cfg_op", "relational"]

    def test_plugin_operator_end_to_end_via_cli(self, tmp_path, monkeypatch):
        """文档承诺的用法：--plugin-dir + --operators <插件算子> 必须端到端可用。"""
        import os
        import shutil
        import subprocess

        from tests.test_platform import MINI_PROJECT

        proj = tmp_path / "proj"
        for rel, content in MINI_PROJECT.items():
            p = proj / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")

        template = ROOT / "metatest" / "plugins" / "templates" / "example_operator_plugin.py"
        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()
        shutil.copy(template, plugin_dir / "example_operator_plugin.py")
        monkeypatch.setenv("METATEST_TRUST_STORE", str(tmp_path / "ts.json"))
        from metatest.config import grant_trust

        grant_trust(proj / "metatest.yaml")
        proc = subprocess.run(
            [sys.executable, "-m", "metatest", "run", "--no-cache", "--no-quality",
             "--plugin-dir", str(plugin_dir), "--operators", "zero_constant"],
            cwd=str(proj), capture_output=True, text=True, timeout=600,
            encoding="utf-8", errors="replace")
        assert proc.returncode in (0, 1), proc.stdout[-1500:]
        results = json.loads((proj / ".metatest/report/results.json").read_text(encoding="utf-8"))
        ops = {m["operator"] for m in results["mutants"]}
        assert ops == {"zero_constant"}, f"应只包含插件算子，实际: {sorted(ops)}"


class TestCacheAtomicWrite:
    """回归：并发保存曾以非原子方式写 cache.json（交错写可损坏 JSON）。"""

    def test_concurrent_save_keeps_valid_json(self, tmp_path):
        from metatest.core.cache import ResultCache
        from metatest.models import Mutant, MutantStatus

        path = tmp_path / "cache.json"
        cfg_like = type("C", (), {"name": "t", "language": "python", "test_cmd": "t",
                                  "test_result_format": "exit_code", "timeout_sec": 10})()

        def worker(offset: int):
            cache = ResultCache(path, enabled=True)
            for i in range(15):
                m = Mutant(path="src/x.py", start_offset=offset * 100 + i,
                           end_offset=offset * 100 + i + 1, lineno=1,
                           operator="probe", original="a", mutated="b")
                m.stable_id()
                m.status = MutantStatus.KILLED
                cache.put(ResultCache.key(cfg_like, m, "h"), m)
                cache.save()

        threads = [threading.Thread(target=worker, args=(k,)) for k in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data.get("version") == 1
        assert len(data.get("entries", {})) > 0

    def test_load_survives_corrupt_file(self, tmp_path):
        from metatest.core.cache import ResultCache

        p = tmp_path / "cache.json"
        p.write_text("{corrupted!!", encoding="utf-8")
        cache = ResultCache(p, enabled=True)  # 不应抛异常
        assert cache.size() == 0
