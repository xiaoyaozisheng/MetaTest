"""规则化变异器（借鉴 universalmutator 的规则驱动思路）。

让任意语言项目（command 适配器接入）也能做语法层变异：用户以 YAML 规则文件
声明"独立符号交换对"，变异器在掩码（注释/字符串）后的源码上定位独立符号并交换。

规则文件格式（mutation.rule_files 指向）：

    rules:
      - operator: relational        # 变异算子名（进报告）
        swaps:
          - ["==", "!="]
          - [">=", ">"]

设计约束：
  * 只做"独立符号"交换（两侧为标识符/数字/右括号等），不做表达式重写，
    避免产生语法错误变异体；
  * 默认掩码 //、#、!-->、/* */、--[[ ]] 与 "..." / '...' 字面量
    （Go/Rust/JS/C 系注释通吃；额外语言可通过 swap 正则自适配）；
  * 变异点定位精度低于 AST —— 报告中 engine 记为 "rules"，
    用于与 AST 级得分区分（与词法回退同一审计口径）。
"""

from __future__ import annotations

import re
from pathlib import Path

from metatest.errors import MutationError
from metatest.mutators.base import Mutation, Mutator, MutantSpec, line_starts, offset_to_lineno


def load_rule_files(paths, base_dir=None) -> list:
    """加载 YAML 规则文件 → [{operator, swaps}]，去重合并。相对路径基于 base_dir（项目根）。"""
    import yaml

    if isinstance(paths, (str, Path)):
        paths = [paths]
    base = Path(base_dir) if base_dir else Path.cwd()
    rules = []
    seen = set()
    for p in paths:
        path = Path(p)
        if not path.is_absolute():
            path = base / path
        if not path.exists():
            raise MutationError(f"规则文件不存在: {p}")
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as e:
            raise MutationError(f"规则文件 YAML 解析失败: {p}: {e}")
        for rule in data.get("rules", []) or []:
            name = str(rule.get("operator", "")).strip()
            swaps = rule.get("swaps") or []
            if not name or not swaps:
                continue
            norm = []
            for pair in swaps:
                if isinstance(pair, (list, tuple)) and len(pair) == 2:
                    a, b = str(pair[0]), str(pair[1])
                    if a and b and a != b:
                        norm.append((a, b))
            if not norm:
                continue
            key = (name, tuple(sorted(norm)))
            if key in seen:
                continue
            seen.add(key)
            rules.append({"operator": name, "swaps": norm})
    return rules


class RuleMutator(Mutator):
    """规则驱动的语言无关变异器（行级掩码扫描 + 独立符号交换）。"""

    language = "rules"
    file_exts = ("*",)  # 由 include_globs 决定

    def __init__(self, rules: list):
        self.rules = rules

    def generate_for_file(self, rel_path: str, source: str, operators: list) -> list:
        # 规则文件本身就是用户的显式选择：不按内置算子白名单过滤
        masked = _mask(source)
        mutations = []
        for rule in self.rules:
            for sym_from, sym_to in rule["swaps"]:
                mutations.extend(
                    _swap_standalone(masked, source, sym_from, sym_to,
                                     rule["operator"])
                )
        return self._finalize(rel_path, source, mutations)

    def _finalize(self, rel_path, source, mutations) -> list:
        specs, seen = [], set()
        starts = line_starts(source)
        for m in mutations:
            key = (m.start, m.end, m.replacement)
            if key in seen:
                continue
            seen.add(key)
            specs.append(MutantSpec(
                path=rel_path,
                start_offset=m.start,
                end_offset=m.end,
                lineno=offset_to_lineno(starts, m.start),
                operator=m.operator,
                original=source[m.start:m.end],
                mutated=m.replacement,
                description=m.description,
                engine="rules",
            ))
        specs.sort(key=lambda s: (s.start_offset, s.end_offset))
        return specs


def _mask(text: str) -> str:
    """掩码注释与字符串字面量（多语言注释约定）。"""
    chars = list(text)
    for line_match in re.finditer(r"(?m)^[ \t]*#[^\n]*", text):
        for k in range(line_match.start(), line_match.end()):
            if chars[k] != "\n":
                chars[k] = " "
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == "/" and text[i + 1:i + 2] == "/":
            j = text.find("\n", i)
            j = n if j < 0 else j
            for k in range(i, j):
                chars[k] = " "
            i = j
        elif c == "-" and text[i + 1:i + 3] == "--":
            j = text.find("]]", i + 3)  # Lua 块注释
            j = n if j < 0 else j + 2
            for k in range(i, j):
                if text[k] != "\n":
                    chars[k] = " "
            i = j
        elif c == "/" and text[i + 1:i + 2] == "*":
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            for k in range(i, j):
                if text[k] != "\n":
                    chars[k] = " "
            i = j
        elif c in ('"', "'"):
            q = c
            j = i + 1
            while j < n:
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == q:
                    break
                j += 1
            j = min(j + 1, n)
            for k in range(i + 1, max(i + 1, j - 1)):
                if text[k] != "\n":
                    chars[k] = " "
            i = j
        else:
            i += 1
    return "".join(chars)


_ID_OK = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_)$")
_OP_CHARS = set("=+-*/%<>&|^~!?:.,")
_PREFIX_SYMBOLS = {"!", "~"}


def _prev_nonspace(masked, i):
    j = i - 1
    while j >= 0 and masked[j] in " \t\n\r":
        j -= 1
    return masked[j] if j >= 0 else ""


def _next_nonspace(masked, i):
    j = i + 1
    while j < len(masked) and masked[j] in " \t\n\r":
        j += 1
    return masked[j] if j < len(masked) else ""


def _swap_standalone(masked: str, source: str, sym_from: str, sym_to: str,
                     operator: str) -> list:
    """在掩码文本中定位独立符号，返回 Mutation 列表。

    中缀符号（==、&&、+…）：两侧最近的非空字符需为标识符/数字/')' 与 标识符/数字/'('；
    前缀符号（!、~）：右侧非空字符需为标识符，左侧不得为标识符（排除 a!=b 内部）。
    """
    out = []
    i = 0
    n = len(masked)
    slen = len(sym_from)
    prefix = sym_from in _PREFIX_SYMBOLS
    while i <= n - slen:
        if masked[i:i + slen] != sym_from:
            i += 1
            continue
        if _part_of_longer(masked, i, slen, sym_from):
            i += 1
            continue
        if prefix:
            nxt = _next_nonspace(masked, i + slen)
            prv = _prev_nonspace(masked, i)
            if nxt and (nxt.isalnum() or nxt in "_(") and not (prv.isalnum() or prv in "_)$"):
                out.append(Mutation(i, i + slen, sym_to, operator,
                                    f"规则交换 {sym_from} → {sym_to or '（删除）'}"))
                i += max(1, slen)
                continue
        else:
            prev = _prev_nonspace(masked, i)
            nxt = _next_nonspace(masked, i + slen)
            prev_ok = bool(prev) and (prev.isalnum() or prev in "_)$")
            next_ok = bool(nxt) and (nxt.isalnum() or nxt in "_(")
            if prev_ok and next_ok:
                out.append(Mutation(i, i + slen, sym_to, operator,
                                    f"规则交换 {sym_from} → {sym_to}"))
                i += slen
                continue
        i += 1
    return out


def _part_of_longer(masked: str, i: int, slen: int, sym: str) -> bool:
    """符号是否是更长运算符的一部分（== vs ===，< vs <= 等）。"""
    ops2 = {"==", "!=", "<=", ">=", "&&", "||", "->", "::", "**", "++", "--", "<<", ">>"}
    n = len(masked)
    before = masked[i - 1] if i > 0 else ""
    after = masked[i + slen] if i + slen < n else ""
    # 两字符符号的第三字符相同或构成另一运算符 → 更长 token
    if slen == 2:
        if (before + sym) in ops2 or (sym + after) in ops2:
            return True
        if sym[0] == sym[1] and after == sym[0]:
            return True  # === / &&& 类
        return False
    if slen == 1:
        pair = before + sym
        if pair in ops2 or (sym + after) in ops2:
            return True
        if before == sym and sym in "+-<>&|=":
            return True  # ++、--、<<、== 等重复符号
        return False
    return False
