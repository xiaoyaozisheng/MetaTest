"""增量变异（PRD P0：按改动文件/函数筛选变异体）。

来源两种：
  * git diff（--diff-ref REF；默认 HEAD，即当前未提交改动）
  * --changed-files 显式文件列表（CI 无 git 场景）

文件级 + 函数级：Python 用 AST 定位改动行所在函数（函数内任一改动 → 该函数
整体相关）；C 用改动行范围（hunk ± padding）。
"""

from __future__ import annotations

import ast
import fnmatch
import re
import subprocess
from pathlib import Path

from metatest.errors import MetaTestError
from metatest.mutators.base import line_starts, offset_to_lineno

_HUNK_RE = re.compile(r"^@@ -\d+(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def changed_targets(project_root, diff_ref=None, changed_files=None) -> dict:
    """返回 {相对路径: [(起行, 止行), ...]}（1 起始闭区间；空列表表示整文件相关）。"""
    root = Path(project_root)
    if changed_files:
        return {f.replace("\\", "/"): [] for f in changed_files}
    if diff_ref is None:
        diff_ref = "HEAD"
    try:
        proc = subprocess.run(
            ["git", "diff", "--unified=0", "--no-color", diff_ref],
            cwd=str(root), capture_output=True, text=True, timeout=120, encoding="utf-8", errors="replace",
        )
    except FileNotFoundError:
        raise MetaTestError("增量模式需要 git，但未找到 git 命令；可改用 --changed-files 显式指定改动文件")
    except subprocess.TimeoutExpired:
        raise MetaTestError(f"git diff 超时（ref={diff_ref}）")
    if proc.returncode != 0:
        raise MetaTestError(f"git diff 失败（ref={diff_ref}）: {proc.stderr.strip()[:300]}")
    return _parse_diff(proc.stdout)


def _parse_diff(diff_text: str) -> dict:
    targets: dict = {}
    current_file = None
    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[6:].strip().strip('"').replace("\\", "/")
            targets.setdefault(current_file, [])
        elif line.startswith("+++ /dev/null") or line.startswith("+++ "):
            current_file = None
        elif current_file and line.startswith("@@"):
            m = _HUNK_RE.match(line)
            if not m:
                continue
            start = int(m.group(2))
            count = int(m.group(3) or "1")
            if count == 0:
                continue  # 纯删除行，不产生新代码行
            targets[current_file].append((start, start + count - 1))
    return targets


def python_function_ranges(source: str, changed_hunks: list) -> list:
    """Python：返回与改动行相交的函数/类方法的行区间。"""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    ranges = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for (s, e) in changed_hunks:
                if node.lineno <= e and node.end_lineno >= s:
                    ranges.append((node.lineno, node.end_lineno))
                    break
    return ranges


def filter_mutants(mutants, targets: dict, project_root, function_level: bool = True,
                   pad: int = 3) -> tuple:
    """筛选与改动相关的变异体。

    返回 (kept_mutants, stats)；stats 包含 kept/filtered 计数与按文件统计。
    """
    from metatest.models import MutantStatus

    kept, filtered = [], 0
    per_file_kept: dict = {}
    glob_cache: dict = {}

    def file_matches(path: str) -> bool:
        if path in targets:
            return True
        # 支持路径前缀（目录级变更，如 src/）
        for t in targets:
            if t.endswith("/") and path.startswith(t):
                return True
        return False

    for m in mutants:
        if not file_matches(m.path):
            filtered += 1
            continue
        hunks = targets.get(m.path, [])
        if not hunks:
            # 整文件相关
            kept.append(m)
            per_file_kept[m.path] = per_file_kept.get(m.path, 0) + 1
            continue
        related = _expand_hunks(m.path, hunks, project_root, function_level, pad)
        if any(s <= m.lineno <= e for (s, e) in related):
            kept.append(m)
            per_file_kept[m.path] = per_file_kept.get(m.path, 0) + 1
        else:
            filtered += 1
    stats = {
        "total": len(mutants),
        "kept": len(kept),
        "filtered": filtered,
        "changed_files": sorted(targets.keys()),
        "per_file_kept": per_file_kept,
    }
    return kept, stats


def _expand_hunks(rel_path: str, hunks: list, project_root, function_level: bool, pad: int) -> list:
    expanded = [(max(1, s - pad), e + pad) for (s, e) in hunks]
    if not function_level:
        return expanded
    src = Path(project_root) / rel_path
    if not src.exists() or src.suffix != ".py":
        return expanded
    try:
        source = src.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return expanded
    expanded.extend(python_function_ranges(source, hunks))
    return expanded
