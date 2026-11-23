"""变异器框架：变异算子注册表、变异候选与补丁应用。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from metatest.config import OPERATORS
from metatest.errors import MutationError


@dataclass
class MutantSpec:
    """变异候选（尚未执行）。"""

    path: str            # 项目相对路径（posix 风格）
    start_offset: int    # 字符偏移 [start, end)
    end_offset: int
    lineno: int          # 1 起始行号
    operator: str
    original: str
    mutated: str
    description: str = ""
    engine: str = ""     # 生成引擎：ast / tree_sitter / fallback（报告与可信度统计用）

    def to_mutant(self) -> "metatest.models.Mutant":  # noqa: F821
        from metatest.models import Mutant

        m = Mutant(
            path=self.path,
            start_offset=self.start_offset,
            end_offset=self.end_offset,
            lineno=self.lineno,
            operator=self.operator,
            original=self.original,
            mutated=self.mutated,
            description=self.description,
            engine=self.engine,
        )
        m.stable_id()
        return m


@dataclass
class Mutation:
    """变异器内部产出的原始变异（字符区间 + 替换文本）。"""

    start: int
    end: int
    replacement: str
    operator: str
    description: str


class Mutator:
    """语言变异器基类。子类实现 generate_for_file。"""

    language = "base"

    def generate_for_file(self, rel_path: str, source: str, operators: list) -> list:
        raise NotImplementedError

    def generate(self, files: dict, operators: list) -> list:
        """files: {rel_path: source_text} -> [MutantSpec]"""
        specs = []
        for rel_path, source in files.items():
            specs.extend(self.generate_for_file(rel_path, source, operators))
        return specs


def apply_spec(source: str, spec: MutantSpec) -> str:
    """把变异应用到源码文本。校验原片段匹配，防止偏移错位。"""
    seg = source[spec.start_offset:spec.end_offset]
    if seg != spec.original:
        raise MutationError(
            f"变异应用失败（偏移不匹配）: {spec.path}:{spec.lineno} "
            f"期望 {spec.original!r} 实际 {seg!r}"
        )
    return source[:spec.start_offset] + spec.mutated + source[spec.end_offset:]


def line_starts(text: str) -> list:
    """每个起始行（1-based）的字符偏移表，末尾附加一个哨兵值。"""
    starts = [0]
    for i, ch in enumerate(text):
        if ch == "\n":
            starts.append(i + 1)
    starts.append(len(text) + 1)
    return starts


def offset_to_lineno(starts: list, offset: int) -> int:
    lo, hi = 0, len(starts) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if starts[mid] <= offset:
            lo = mid
        else:
            hi = mid - 1
    return lo + 1


# ---------------------------------------------------------------------------
# 第三方/插件算子注册（PRD FR-10 插件机制）
# ---------------------------------------------------------------------------

_custom_python_operators: dict = {}  # name -> callable(node, ctx) -> [Mutation]
_custom_c_operators: dict = {}


def register_python_operator(name: str, fn: Callable) -> None:
    """注册新的 Python 变异算子（供插件调用）。

    fn(node: ast.AST, ctx: PythonMutationContext) -> list[Mutation]
    """
    _custom_python_operators[name] = fn


def register_c_operator(name: str, fn: Callable) -> None:
    """注册新的 C 变异算子（供插件调用）。

    fn(node, ctx: CMutationContext) -> list[Mutation]
    """
    _custom_c_operators[name] = fn


def custom_python_operators() -> dict:
    return dict(_custom_python_operators)


def custom_c_operators() -> dict:
    return dict(_custom_c_operators)


def known_operators() -> dict:
    return {**OPERATORS, **{k: "插件算子" for k in _custom_python_operators}}


def describe_operator(name: str) -> str:
    if name in OPERATORS:
        return OPERATORS[name]
    if name in _custom_python_operators or name in _custom_c_operators:
        return "自定义算子"
    return "未知算子"


def read_source(path: Path) -> str:
    """读取源码文本（utf-8 优先，兼容 BOM/GBK）。"""
    raw = Path(path).read_bytes()
    for enc in ("utf-8-sig", "utf-8", "gbk", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")
