"""变异执行引擎（PRD FR-05 / FR-06）。

流程：基线测试 → 增量筛选 → 等价标记 → 缓存复用 → 并行执行（沙箱隔离、
超时终止）→ 结果判定与得分。
"""

from __future__ import annotations

import ast
import fnmatch
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from metatest.adapters.base import BaseAdapter
from metatest.config import ProjectConfig
from metatest.core.cache import ResultCache
from metatest.core.sandbox import Sandbox
from metatest.models import (
    AnalysisResult,
    Mutant,
    MutantStatus,
    RunOutcome,
    TestRunResult,
)
from metatest.mutators.base import MutantSpec, apply_spec, read_source

STATUS_ICONS = {
    MutantStatus.KILLED: "killed",
    MutantStatus.SURVIVED: "survived",
    MutantStatus.TIMEOUT: "timeout",
    MutantStatus.EQUIVALENT: "equivalent",
    MutantStatus.ERROR: "error",
}

# 启发式：这些 dunder 方法中的返回值/实参变异大概率等价
_SUSPECT_DUNDERS = ("__repr__", "__str__", "__hash__", "__eq__", "__ne__")
_SUSPECT_OPS = ("return_value", "none_replacement", "statement_deletion")


class MutationEngine:
    def __init__(self, config: ProjectConfig, project_root, adapter: BaseAdapter, progress=None):
        self.config = config
        self.project_root = Path(project_root)
        self.adapter = adapter
        self.progress = progress or (lambda msg: print(msg, flush=True))
        self._suite_size = None

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------

    def run(
        self,
        mutants: list,
        incremental_targets=None,
        incremental_source="",
        function_level: bool = True,
        no_cache: bool = False,
        equivalents_file=None,
    ) -> AnalysisResult:
        start = time.monotonic()
        analysis = AnalysisResult(project_name=self.config.name, started_at=time.time())
        analysis.mutants = mutants
        analysis.incremental = None
        analysis.test_selection = None
        analysis.strategy = getattr(self.adapter, "mutator_info", None)
        sources = self._load_sources(mutants)

        # 1. 增量筛选
        if incremental_targets is not None:
            from metatest.core.incremental import filter_mutants

            kept, stats = filter_mutants(mutants, incremental_targets, self.project_root,
                                         function_level=function_level)
            stats["source"] = incremental_source
            stats["function_level"] = function_level
            analysis.incremental = stats
            dropped_ids = {id(m) for m in mutants} - {id(m) for m in kept}
            for m in mutants:
                if id(m) in dropped_ids:
                    m.status = MutantStatus.NOT_RUN
                    m.message = "增量过滤：与本次改动无关"
            mutants = kept

        # 2. 基线测试（未变异）
        baseline = self._run_baseline()
        analysis.baseline = baseline
        if baseline.outcome in (RunOutcome.FAIL, RunOutcome.ERROR, RunOutcome.TIMEOUT, RunOutcome.ALL_SKIPPED):
            reason = {
                RunOutcome.FAIL: "基线测试存在失败：变异结果无法解释，请先修复测试",
                RunOutcome.ERROR: "基线测试无法执行",
                RunOutcome.TIMEOUT: "基线测试超时",
                RunOutcome.ALL_SKIPPED: "基线测试全部被跳过：跳过不等于通过，变异评估拒绝执行",
            }[baseline.outcome]
            for m in mutants:
                m.status = MutantStatus.ERROR
                m.message = reason
            analysis.duration_sec = time.monotonic() - start
            self.progress(f"[baseline] {reason} → 全部变异标记为 error")
            return analysis

        # 3. 人工等价标记 + 启发式可疑标记
        eq_entries = self._load_equivalents(equivalents_file)
        for m in mutants:
            if match_equivalent(m, eq_entries):
                m.status = MutantStatus.EQUIVALENT
                m.message = "人工标记为等价变异"
        mark_suspect_equivalents(mutants, sources)

        # 3.5 测试关联筛选（增强：mutant → covering tests）
        test_map = None
        if self.config.mutation.test_selection and mutants:
            if self.config.language != "python":
                self.progress("[testmap] test_selection 目前仅支持 Python/pytest 项目，已跳过")
            else:
                from metatest.core.testmap import build_test_map

                self.progress("[testmap] 采集每个测试的行级覆盖（--cov-context=test）…")
                test_map = build_test_map(self.project_root, self.config, self.config.timeout_sec)
                analysis.test_selection = {
                    "tests": test_map.test_count,
                    "files": test_map.file_count,
                    "build_sec": round(test_map.build_sec, 1),
                }
                self.progress(
                    f"[testmap] {test_map.test_count} 个测试 × {test_map.file_count} 个源码文件，"
                    f"构建耗时 {test_map.build_sec:.1f}s"
                )
                self._suite_size = test_map.test_count

        # 4. 缓存
        cache = ResultCache(
            self.project_root / self.config.cache.dir / "cache.json",
            enabled=self.config.cache.enabled and not no_cache,
        )
        pending = []
        zero_covered = 0
        for m in mutants:
            if m.status == MutantStatus.EQUIVALENT:
                continue
            patched = self._patched_text(m, sources)
            if patched is None:
                m.status = MutantStatus.ERROR
                m.message = "变异应用失败或源文件缺失"
                continue
            # 零覆盖快判：没有任何测试执行过该行 → 不可能被杀死
            if test_map is not None:
                covering = test_map.covering(m.path, m.lineno)
                m.covered_by = len(covering)
                if not covering:
                    m.status = MutantStatus.SURVIVED
                    m.message = "零覆盖：无任何测试执行该行（test_selection 快判）"
                    zero_covered += 1
                    continue
            key = ResultCache.key(self.config, m, _hash_text(patched))
            entry = cache.get(key)
            if entry:
                m.status = MutantStatus(entry["status"])
                m.duration_sec = entry.get("duration_sec", 0.0)
                m.message = entry.get("message", "") + "（缓存）"
                m.failed_tests = entry.get("failed_tests", [])
                m.cached = True
            else:
                pending.append((m, patched, key))
        if zero_covered:
            self.progress(f"[testmap] {zero_covered} 个变异体零覆盖，直接判 survived（跳过执行）")

        # 5. 并行执行
        total = len(pending)
        done = 0
        parallelism = max(1, self.config.parallelism)
        if total:
            self.progress(
                f"[run] 变异体 {len(mutants)} 个；待执行 {total}（并行 {parallelism}，超时 {self.config.timeout_sec}s）"
            )
            with ThreadPoolExecutor(max_workers=parallelism) as pool:
                futures = {}
                for m, text, key in pending:
                    tids = test_map.covering(m.path, m.lineno) if test_map else None
                    futures[pool.submit(self._execute_mutant, m, text, self.config.timeout_sec, tids)] = (m, key)
                try:
                    for fut in as_completed(futures):
                        mutant, key = futures[fut]
                        try:
                            status, message, run = fut.result()
                        except Exception as e:  # 沙箱/意外异常 → error
                            status, message, run = MutantStatus.ERROR, f"执行异常: {e}", None
                        mutant.status = status
                        mutant.message = message
                        if run is not None:
                            mutant.duration_sec = run.duration_sec
                            mutant.failed_tests = list(run.failing_tests)
                        cache.put(key, mutant)
                        done += 1
                        self.progress(
                            f"[{done}/{total}] {status.value:9s} {mutant.location} "
                            f"{mutant.operator} ({mutant.duration_sec:.1f}s)"
                        )
                except KeyboardInterrupt:
                    pool.shutdown(wait=True, cancel_futures=True)
                    raise
        cache.save()

        analysis.duration_sec = time.monotonic() - start
        return analysis

    # ------------------------------------------------------------------
    # 内部步骤
    # ------------------------------------------------------------------

    def _run_baseline(self) -> TestRunResult:
        self.progress(f"[baseline] 运行基线测试: {self.config.test_cmd}")
        with Sandbox.create(self.project_root, self.config.sandbox.copy_exclude) as sb:
            run = self.adapter.run_tests(sb.path, self.config.timeout_sec)
        self.progress(
            f"[baseline] {run.outcome.value}（tests={run.tests} failures={run.failures} "
            f"errors={run.errors} skipped={run.skipped}，{run.duration_sec:.1f}s）"
        )
        if run.tests == 0 and run.outcome in (RunOutcome.FAIL, RunOutcome.ERROR):
            # 0 用例多半不是“测试失败”，而是命令跑不起来 / 路径或依赖不对，给出可诊断线索
            tail = (run.output_tail or "").strip().splitlines()
            hint = tail[-1][:200] if tail else f"exit_code={run.exit_code}"
            self.progress(
                f"[baseline] 命令未收集到任何测试用例（exit_code={run.exit_code}）：{hint}\n"
                f"[baseline] 排查：test_cmd 是否指向正确的解释器/测试目录，依赖（pytest 等）是否已安装"
            )
        return run

    def _load_sources(self, mutants) -> dict:
        sources = {}
        for m in mutants:
            if m.path in sources:
                continue
            p = self.project_root / m.path
            try:
                sources[m.path] = read_source(p)
            except (OSError, UnicodeError):
                sources[m.path] = None
        return sources

    def _patched_text(self, mutant: Mutant, sources: dict):
        src = sources.get(mutant.path)
        if not src:
            return None
        spec = MutantSpec(
            path=mutant.path, start_offset=mutant.start_offset, end_offset=mutant.end_offset,
            lineno=mutant.lineno, operator=mutant.operator,
            original=mutant.original, mutated=mutant.mutated,
        )
        try:
            return apply_spec(src, spec)
        except Exception:
            return None

    def _execute_mutant(self, mutant: Mutant, patched_text: str, timeout: float,
                        test_ids=None):
        with Sandbox.create(self.project_root, self.config.sandbox.copy_exclude) as sb:
            target = sb.path / mutant.path
            target.parent.mkdir(parents=True, exist_ok=True)
            # 按字节写：避免 Windows 文本模式把 CRLF 翻译成 CRCRLF
            target.write_bytes(patched_text.encode("utf-8"))
            run = self.adapter.run_tests(sb.path, timeout, test_ids=test_ids)
        status, message = map_run_to_status(run)
        if test_ids:
            message = f"筛选测试 {len(test_ids)}/{self._suite_size or '?'}：{message}"
        return status, message, run

    def _load_equivalents(self, equivalents_file) -> list:
        import json

        if equivalents_file is None:
            equivalents_file = self.project_root / self.config.cache.dir / "equivalents.yaml"
        path = Path(equivalents_file)
        if not path.exists():
            return []
        import yaml

        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            return []
        entries = data.get("equivalents", []) if isinstance(data, dict) else data
        return [str(e) for e in (entries or [])]


def map_run_to_status(run: TestRunResult):
    """把一次测试运行映射为变异判定（PRD FR-06）。

    元测试要点：跳过 ≠ 通过。全部跳过的运行不能证明变异存活。
    """
    if run.outcome == RunOutcome.FAIL:
        failed = ", ".join(run.failing_tests[:3]) or f"exit_code={run.exit_code}"
        return MutantStatus.KILLED, f"测试发现变异（{failed}）"
    if run.outcome in (RunOutcome.PASS, RunOutcome.PASS_WITH_SKIPS):
        note = "（含跳过用例）" if run.skipped else ""
        return MutantStatus.SURVIVED, f"全部测试通过{note}，测试漏测该变异"
    if run.outcome == RunOutcome.TIMEOUT:
        return MutantStatus.TIMEOUT, f"测试执行超时（>{timeout_fmt(run.duration_sec)}s）"
    if run.outcome == RunOutcome.ALL_SKIPPED:
        return MutantStatus.ERROR, "所有测试被跳过：跳过不等于通过，无法评估该变异"
    tail = (run.output_tail or "").strip().splitlines()
    snippet = tail[-1][:120] if tail else ""
    return MutantStatus.ERROR, f"构建/执行错误 exit_code={run.exit_code} {snippet}".strip()


def timeout_fmt(seconds: float) -> str:
    return f"{seconds:.1f}"


def match_equivalent(mutant: Mutant, entries: list) -> bool:
    """匹配人工等价标记：支持完整 id、path:line:operator、path:line 与通配。"""
    triple = f"{mutant.path}:{mutant.lineno}:{mutant.operator}"
    double = f"{mutant.path}:{mutant.lineno}"
    for e in entries:
        e = e.strip()
        if not e or e.startswith("#"):
            continue
        if e in (mutant.id, triple, double):
            return True
        if any(ch in e for ch in "*?["):
            if fnmatch.fnmatch(mutant.id, e) or fnmatch.fnmatch(triple, e):
                return True
    return False


def mark_suspect_equivalents(mutants: list, sources: dict) -> None:
    """启发式可疑等价标记（不改变判定，只做提示；PRD P1）。"""
    ranges_by_file: dict = {}
    for path, src in sources.items():
        if not src or not path.endswith(".py"):
            continue
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        ranges = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in _SUSPECT_DUNDERS:
                ranges.append((node.lineno, node.end_lineno))
        if ranges:
            ranges_by_file[path] = ranges
    if not ranges_by_file:
        return
    from metatest.mutators.base import line_starts, offset_to_lineno

    for m in mutants:
        ranges = ranges_by_file.get(m.path)
        if not ranges or m.operator not in _SUSPECT_OPS:
            continue
        src = sources.get(m.path) or ""
        lineno = offset_to_lineno(line_starts(src), m.start_offset)
        if any(s <= lineno <= e for (s, e) in ranges):
            m.suspect_equivalent = True
            m.message = (m.message + "；" if m.message else "") + "启发式提示：疑似等价变异（dunder 方法内）"


def _hash_text(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()
