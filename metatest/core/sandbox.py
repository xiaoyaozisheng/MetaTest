"""执行沙箱（PRD FR-05 / 非功能-隔离）：每个变异体在独立工作目录中执行。

默认排除 .git、构建产物、缓存目录等，避免污染主工作区。
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

SANDBOX_IGNORES = (
    ".git", ".hg", ".svn", "__pycache__", ".metatest", ".pytest_cache",
    "node_modules", "build", "dist", "venv", ".venv", "out", "target",
    "*.pyc", "*.pyo", "*.exe", "*.o", "*.obj", "*.dll", "*.so", "*.a", "*.lib",
    ".idea", ".vscode", "*.egg-info", ".mypy_cache", ".ruff_cache",
)


class Sandbox:
    """一次性工作目录副本。"""

    def __init__(self, path: Path):
        self.path = path

    @classmethod
    def create(cls, project_root, extra_excludes=()) -> "Sandbox":
        project_root = Path(project_root)
        ignores = list(SANDBOX_IGNORES) + [str(e) for e in extra_excludes]
        dst = Path(tempfile.mkdtemp(prefix="metast_"))
        shutil.copytree(
            project_root,
            dst,
            ignore=shutil.ignore_patterns(*ignores),
            dirs_exist_ok=True,
        )
        return cls(dst)

    def cleanup(self) -> None:
        shutil.rmtree(self.path, ignore_errors=True)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.cleanup()
        return False
