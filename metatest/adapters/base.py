"""适配器协议（PRD FR-02）。

统一接口：detect()、prepare()、generate_mutants()、run_tests()、parse_result()、cleanup()。
内置适配器：Python、C、Command；第三方通过插件注册扩展。
"""

from __future__ import annotations

import fnmatch
from pathlib import Path

from metatest.config import ProjectConfig
from metatest.errors import AdapterError
from metatest.junit import apply_summary, extract_junit_path, parse_junit
from metatest.models import RunOutcome, TestRunResult
from metatest.mutators.base import MutantSpec, read_source
from metatest.proc import ProcResult, run_command

# 收集源码时默认跳过的目录/文件
DEFAULT_SKIP_DIRS = {
    ".git", ".hg", ".svn", "__pycache__", ".metatest", ".pytest_cache",
    "node_modules", "build", "build-*", "dist", "venv", ".venv", ".idea", ".vscode",
    "cmake-build-debug", "cmake-build-release", "out", "target", ".cache",
}
DEFAULT_SKIP_FILES = ("*.pyc", "*.pyo", "*.exe", "*.o", "*.obj", "*.dll", "*.so", "*.a", "*.lib")


def _skip(name: str) -> bool:
    if name in DEFAULT_SKIP_DIRS or name.startswith("."):
        return True
    for pat in DEFAULT_SKIP_FILES:
        if fnmatch.fnmatch(name, pat):
            return True
    return False


def collect_files(root: Path, roots: list, exts, exclude_globs: list = (), include_globs: list = ()) -> dict:
    """收集 {相对路径(posix): 绝对路径}，应用排除/包含规则。exts=None 表示不过滤后缀。"""
    root = Path(root)
    files = {}
    for src_root in roots:
        base = root / src_root
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            # 只按项目内相对路径判断跳过规则：仓库本身位于 .local/.venv 之类目录下时
            # 不应把整个项目判为“要跳过”
            rel_parts = Path(rel).parts
            if _skip(path.name) or any(_skip(part) for part in rel_parts[:-1]):
                continue
            if exts is not None and Path(rel).suffix.lower() not in exts:
                continue
            from metatest.globutil import match as glob_match

            if any(glob_match(rel, g) for g in exclude_globs):
                continue
            if include_globs and not any(glob_match(rel, g) for g in include_globs):
                continue
            files[rel] = path
    return files


class BaseAdapter:
    """适配器基类：实现 PRD FR-02 统一接口。"""

    name = "base"
    language = None

    def __init__(self, project_root, config: ProjectConfig):
        self.project_root = Path(project_root)
        self.config = config
        self.mutator_info = None  # resolve_mutator 的选择信息（engine 填入 analysis.strategy）

    # -- 协议接口 ---------------------------------------------------------

    @classmethod
    def detect(cls, root, config: ProjectConfig | None = None) -> int:
        """探测项目是否适合本适配器，返回置信度 0-100。"""
        return 0

    def prepare(self) -> None:
        """运行前环境校验，失败抛 AdapterError。"""

    def generate_mutants(self, operators: list) -> list:
        """生成变异候选列表 [MutantSpec]。默认走策略解析（规则文件优先）。"""
        from metatest.mutators import resolve_mutator
        from metatest.mutators.base import read_source

        mutator, info = resolve_mutator(self.config, self.project_root)
        if mutator is None:
            return []
        self.mutator_info = info
        if info.get("strategy") == "rule":
            files = self._collect(self.config.source_roots, None)
        else:
            files = self._collect(self.config.source_roots, tuple(mutator.file_exts))
        sources = {}
        for rel, abs_path in files.items():
            try:
                sources[rel] = read_source(abs_path)
            except (OSError, UnicodeError):
                continue
        specs = mutator.generate(sources, operators)
        if self.config.mutation.include_globs:
            from metatest.globutil import match as glob_match

            specs = [s for s in specs
                     if any(glob_match(s.path, g) for g in self.config.mutation.include_globs)]
        return specs

    def build(self, work_dir, timeout: float) -> ProcResult | None:
        """构建（如需）。返回 None 表示无需构建。"""
        return None

    def run_tests(self, work_dir, timeout: float, test_ids=None) -> TestRunResult:
        """在 work_dir 中构建并运行测试（test_ids 提供时只运行关联测试），返回结构化结果。"""
        build = self.build(work_dir, timeout)
        if build is not None and build.exit_code != 0:
            run = TestRunResult(
                exit_code=build.exit_code,
                duration_sec=build.duration_sec,
                output_tail=build.output_tail,
            )
            run.outcome = RunOutcome.ERROR
            return run
        proc = run_command(
            self._test_command(test_ids),
            cwd=work_dir,
            timeout=timeout,
            env_extra=self.config.env,
        )
        return self.parse_result(work_dir, proc)

    def _test_command(self, test_ids=None) -> str:
        """测试命令；test_ids 子集筛选仅被支持的适配器覆写。"""
        if test_ids:
            logger = __import__("logging").getLogger("metatest")
            logger.warning("适配器 %s 不支持按测试筛选，回退全量运行", self.name)
        return self.config.test_cmd

    def parse_result(self, work_dir, proc: ProcResult) -> TestRunResult:
        """解析测试命令结果：优先 JUnit XML，回退退出码。"""
        run = TestRunResult(
            exit_code=proc.exit_code,
            duration_sec=proc.duration_sec,
            timed_out=proc.timed_out,
            output_tail=proc.output_tail,
        )
        if self.config.test_result_format == "junit_xml":
            junit_rel = self._resolve_junit_path()
            junit_abs = Path(work_dir) / junit_rel
            if junit_abs.exists():
                try:
                    summary = parse_junit(junit_abs)
                    apply_summary(run, summary)
                    run.junit_path = junit_rel
                except ValueError:
                    pass  # 结果文件损坏时回退退出码判定
        run.classify()
        return run

    def cleanup(self) -> None:
        """运行结束清理。"""

    # -- 内部工具 ---------------------------------------------------------

    def _resolve_junit_path(self) -> str:
        if self.config.junit_path:
            return self.config.junit_path
        extracted = extract_junit_path(self.config.test_cmd, default_name="")
        if extracted:
            return extracted
        return "_metatest_junit.xml"

    def _collect(self, roots, exts) -> dict:
        return collect_files(
            self.project_root, roots, exts,
            exclude_globs=tuple(self.config.mutation.exclude_globs),
            include_globs=tuple(self.config.mutation.include_globs),
        )
