"""Python 适配器（PRD FR-03）：pytest / unittest 接入，JUnit XML 统一结果输入。"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

from metatest.adapters.base import BaseAdapter, collect_files
from metatest.errors import AdapterError
from metatest.mutators.base import MutantSpec, read_source


# 命令中裸写的解释器（python / python3 / python3.11），只匹配命令起始或管道/串联之后，
# 避免误伤 --cov=python、路径参数等。
_PY_INVOCATION = re.compile(
    r"(?P<lead>^|&&|\|\||;|\|)\s*(?P<py>python(?:3(?:\.\d+)?)?)(?=\s)"
)


_PYTEST_CACHE: dict = {}
_DISCOVERED: list | None = None


def _has_pytest(exe: str) -> bool:
    if exe in _PYTEST_CACHE:
        return _PYTEST_CACHE[exe]
    try:
        from metatest.proc import run_command

        result = run_command(f'"{exe}" -c "import pytest"', cwd=Path.cwd(), timeout=25)
        ok = result.exit_code == 0
    except Exception:
        ok = False
    _PYTEST_CACHE[exe] = ok
    return ok


def _discover_installs() -> list:
    """扫描常见安装位置（打包成 exe 后 PATH 上往往没有装了 pytest 的解释器）。"""
    global _DISCOVERED
    if _DISCOVERED is not None:
        return _DISCOVERED
    found: list = []
    if sys.platform == "win32":
        import glob
        import os

        patterns = [
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python3*\python.exe"),
            os.path.expandvars(r"%PROGRAMFILES%\Python3*\python.exe"),
            r"C://Python3*//python.exe",
        ]
        for pattern in patterns:
            found.extend(sorted(glob.glob(pattern), reverse=True))
        try:
            from metatest.proc import run_command

            listing = run_command("py -0p", cwd=Path.cwd(), timeout=15)
            for line in (listing.output or "").splitlines():
                match = re.search(r"([A-Za-z]:\\[^\r\n]*?python\.exe)", line, re.IGNORECASE)
                if match:
                    found.append(match.group(1).strip())
        except Exception:
            pass
    else:
        for candidate in ("/usr/bin/python3", "/usr/local/bin/python3", "/opt/homebrew/bin/python3"):
            if Path(candidate).exists():
                found.append(candidate)
    seen, unique = set(), []
    for item in found:
        key = item.lower() if sys.platform == "win32" else item
        if key not in seen and Path(item).exists():
            seen.add(key)
            unique.append(item)
    _DISCOVERED = unique
    return unique


def interpreter_candidates() -> list:
    """候选解释器：已绑定 → 自身解释器 → PATH → 常见安装位置。"""
    candidates: list = []

    def add(path: str | None):
        if path and path not in candidates:
            candidates.append(path)

    for name in ("python", "python3", "py"):
        add(shutil.which(name))
    if not getattr(sys, "frozen", False):
        add(sys.executable)
    for path in _discover_installs():
        add(path)
    return candidates


def test_interpreter(project_root=None, prefer_pytest: bool = True) -> str | None:
    """执行被测项目测试的解释器。

    优先级：用户为该项目的绑定 → 自身解释器/PATH → 常见安装位置中「能 import pytest」的第一个。
    多 Python 环境下 PATH 上的 python 常常不是装了测试依赖的那个，这正是
    “基线测试 0 个用例”最常见的根因。
    """
    if project_root is not None:
        from metatest.interp_store import get_assigned

        assigned = get_assigned(project_root)
        if assigned:
            return assigned

    candidates = interpreter_candidates()
    if not candidates:
        return None
    if prefer_pytest:
        for exe in candidates:
            if _has_pytest(exe):
                return exe
    return candidates[0]


def available_interpreters(project_root=None) -> list:
    """给界面/错误信息用：候选解释器及其 pytest 可用性。"""
    from metatest.interp_store import get_assigned

    assigned = get_assigned(project_root) if project_root is not None else None
    rows = []
    ordered = ([assigned] if assigned else []) + interpreter_candidates()
    seen = set()
    for exe in ordered:
        key = exe.lower() if sys.platform == "win32" else exe
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            "path": exe,
            "pytest": _has_pytest(exe),
            "assigned": exe == assigned,
            "self": exe == sys.executable,
        })
    return rows


def resolve_python_command(cmd: str, executable: str | None = None,
                           project_root=None) -> str:
    """把测试命令里的裸 `python` 解析为可用的解释器。

    背景：`metatest.yaml` 里写 `python -m pytest` 时，子进程按 PATH 查找 `python`，
    在多 Python 环境（虚拟环境、pyenv、Windows 上多个安装）里极易命中一个没装
    pytest 的解释器，表现为“基线测试 0 个用例”。这里统一替换为探测到的可用解释器；
    显式写绝对路径的解释器不会被替换。
    """
    exe = executable or test_interpreter(project_root)
    if not exe:
        return cmd
    quoted = f'"{exe}"' if " " in exe else exe
    return _PY_INVOCATION.sub(lambda m: f"{m.group('lead')}{quoted}", cmd)


class PythonAdapter(BaseAdapter):
    name = "python"
    language = "python"

    @classmethod
    def detect(cls, root, config=None) -> int:
        root = Path(root)
        score = 0
        if (root / "pyproject.toml").exists() or (root / "setup.py").exists():
            score += 40
        if list(root.glob("*.py")):
            score += 20
        if any((root / d).exists() for d in ("src", "tests")):
            score += 40
        return min(score, 100)

    def prepare(self) -> None:
        cmd = self.config.test_cmd
        if "pytest" in cmd:
            exe = test_interpreter(self.project_root)
            if not exe or not _has_pytest(exe):
                tried = "、".join(f"{i['path']}（pytest {'可用' if i['pytest'] else '缺失'}）"
                                  for i in available_interpreters(self.project_root))
                raise AdapterError(
                    "找不到可用的 pytest 解释器。已检查：" + (tried or "无") +
                    "。请在 metatest.yaml 的 test_cmd 中使用绝对路径解释器，"
                    "或为其中一个解释器安装 pytest（pip install pytest）"
                )
        if self.config.test_result_format == "junit_xml" and "junit" not in cmd and "pytest" not in cmd:
            # unittest 直跑无法产出 JUnit XML；提示但不阻塞（回退退出码判定）
            import logging

            logging.getLogger("metatest").warning(
                "test_cmd 未使用 pytest 且未配置 junit 输出，结果将按退出码判定（无用例级明细）"
            )

    def generate_mutants(self, operators: list) -> list:
        # 走统一策略解析（规则文件优先，其次 AST）；检查在 base 中完成
        return super().generate_mutants(operators)

    def _test_command(self, test_ids=None) -> str:
        """pytest 命令组装：解释器解析、junitxml 注入、fail_fast、测试子集筛选。"""
        cmd = resolve_python_command(self.config.test_cmd, project_root=self.project_root)
        if "pytest" in cmd and "junit" not in cmd and self.config.test_result_format == "junit_xml":
            # junitxml 需要绝对路径占位，运行时才知晓 work_dir；注入标记由 run_tests 处理
            cmd = cmd + " --junitxml {_metatest_junit}"
        if self.config.mutation.fail_fast and "-x" not in cmd.split() and " -x" not in cmd:
            cmd = f"{cmd} -x"
        if test_ids and "pytest" in cmd:
            quoted = " ".join(f'"{t}"' for t in test_ids)
            cmd = f"{cmd} {quoted}"
        return cmd

    def run_tests(self, work_dir, timeout: float, test_ids=None):
        work_dir = Path(work_dir)
        cmd = self._test_command(test_ids)
        junit_abs = (work_dir / "_metatest_junit.xml").resolve()
        cmd = cmd.replace("{_metatest_junit}", str(junit_abs))
        build = self.build(work_dir, timeout)
        if build is not None and build.exit_code != 0:
            from metatest.models import RunOutcome, TestRunResult

            run = TestRunResult(exit_code=build.exit_code, duration_sec=build.duration_sec,
                                output_tail=build.output_tail)
            run.outcome = RunOutcome.ERROR
            return run
        from metatest.proc import run_command

        env = {"PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1"}
        proc = run_command(cmd, cwd=work_dir, timeout=timeout, env_extra={**env, **self.config.env})
        return self.parse_result(work_dir, proc)
