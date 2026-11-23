"""测试关联筛选（mutant → covering tests）。

基于 pytest-cov 的动态覆盖率上下文（--cov-context=test）一次性采集
"每个测试执行了哪些源码行"，构建 行 → 测试 映射；变异执行时只运行
覆盖该变异行的测试，零覆盖变异体直接判 survived（无需执行）。

语义与适用范围：
  * 结果与全量运行一致的前提是测试确定性、无跨测试耦合（与增量模式同一前提）；
  * 仅支持 test_cmd 含 pytest 的 Python 项目；fixture setup/teardown 行不计入；
  * C 侧等价能力需 gcov 逐测试采集，暂未内置（见 docs/limitations.md）。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from metatest.core.sandbox import Sandbox
from metatest.errors import MetaTestError
from metatest.proc import run_command

logger = logging.getLogger("metatest")


@dataclass
class TestMap:
    """行级测试映射：{rel_path: {lineno: [test_node_id, ...]}}。"""

    line_to_tests: dict = field(default_factory=dict)
    test_count: int = 0
    file_count: int = 0
    build_sec: float = 0.0

    def covering(self, rel_path: str, lineno: int) -> list:
        """返回覆盖 (文件, 行) 的测试 node id 列表。"""
        by_line = self.line_to_tests.get(rel_path)
        if not by_line:
            return []
        return sorted(by_line.get(lineno, set()))

    def covering_lines(self, rel_path: str) -> set:
        by_line = self.line_to_tests.get(rel_path)
        return set(by_line or {})


def build_test_map(project_root, config, timeout: float | None = None) -> TestMap:
    """在沙箱中以 --cov-context=test 运行一次测试套件，构建行级映射。"""
    if "pytest" not in config.test_cmd:
        raise MetaTestError(
            "test_selection 需要基于 pytest 的覆盖率上下文（test_cmd 须包含 pytest）"
        )
    timeout = timeout or config.timeout_sec
    started = __import__("time").monotonic()
    cov_flags = [f"--cov={r}" for r in config.source_roots]
    from metatest.adapters.python_adapter import resolve_python_command

    # 与 Python 适配器一致：裸 python 解析为运行 MetaTest 的解释器（保证 pytest-cov 可用）
    test_cmd = resolve_python_command(config.test_cmd, project_root=project_root)
    cmd = (
        f'{test_cmd} {" ".join(cov_flags)} --cov-context=test --cov-report='
    )
    with Sandbox.create(project_root, config.sandbox.copy_exclude) as sb:
        proc = run_command(cmd, cwd=sb.path, timeout=timeout,
                           env_extra={"PYTHONDONTWRITEBYTECODE": "1", **config.env})
        db_path = sb.path / ".coverage"
        if proc.timed_out:
            raise MetaTestError("构建测试映射超时（coverage 上下文采集未完成）")
        if not db_path.exists():
            raise MetaTestError(
                f"未生成 .coverage 数据（exit_code={proc.exit_code}）。"
                "请确认 pytest-cov 已安装：pip install pytest-cov"
            )
        mapping = _parse_coverage_db(db_path, sb.path, config)
    mapping.build_sec = __import__("time").monotonic() - started
    mapping.test_count = len({
        tid for by_line in mapping.line_to_tests.values() for tids in by_line.values() for tid in tids
    })
    mapping.file_count = len(mapping.line_to_tests)
    return mapping


def _parse_coverage_db(db_path: Path, sandbox_root: Path, config) -> TestMap:
    from coverage import CoverageData

    # 先用只读实例拿全量清单
    probe = CoverageData(str(db_path))
    probe.read()
    source_roots = [Path(r).as_posix().rstrip("/") for r in config.source_roots]
    measured = [
        f for f in probe.measured_files()
        if _rel_to_root(f, sandbox_root) is not None
    ]
    tm = TestMap()
    for ctx in probe.measured_contexts():
        if not ctx or not ctx.endswith("|run"):
            continue  # 只取测试主体运行；fixture setup/teardown 不计入
        test_id = ctx[: -len("|run")]
        # 注意：CoverageData 的查询缓存不随 set_query_context 失效，
        # 必须为每个上下文新建实例，否则会返回聚合行集
        data = CoverageData(str(db_path))
        data.read()
        data.set_query_context(ctx)
        for abs_file in measured:
            rel = _rel_to_root(abs_file, sandbox_root)
            if rel is None or not _in_source_roots(rel, source_roots):
                continue
            lines = data.lines(abs_file) or []
            if not lines:
                continue
            by_line = tm.line_to_tests.setdefault(rel, {})
            for lineno in lines:
                by_line.setdefault(int(lineno), set()).add(test_id)
    return tm


def _rel_to_root(abs_path, root: Path):
    try:
        return Path(abs_path).resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return None


def _in_source_roots(rel: str, source_roots: list) -> bool:
    for r in source_roots:
        if rel == r or rel.startswith(r + "/"):
            return True
    return False
