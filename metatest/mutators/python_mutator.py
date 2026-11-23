"""Python AST 变异器（PRD FR-03，附录 12 算子清单）。

基于 ast 模块生成变异体，每个变异体是一处最小文本替换，
应用后保证语法有效（生成时用 ast.parse 校验）。
"""

from __future__ import annotations

import ast
import re

from metatest.mutators.base import (
    Mutation,
    Mutator,
    MutantSpec,
    custom_python_operators,
    line_starts,
    offset_to_lineno,
)

RELATIONAL_SWAP = {
    ast.Gt: ast.LtE,
    ast.LtE: ast.Gt,
    ast.Lt: ast.GtE,
    ast.GtE: ast.Lt,
    ast.Eq: ast.NotEq,
    ast.NotEq: ast.Eq,
}
RELATIONAL_SYMBOL = {
    ast.Gt: ">",
    ast.GtE: ">=",
    ast.Lt: "<",
    ast.LtE: "<=",
    ast.Eq: "==",
    ast.NotEq: "!=",
}
ARITHMETIC_SWAP = {
    ast.Add: ast.Sub,
    ast.Sub: ast.Add,
    ast.Mult: ast.Div,
    ast.Div: ast.Mult,
}
ARITHMETIC_SYMBOL = {
    ast.Add: "+",
    ast.Sub: "-",
    ast.Mult: "*",
    ast.Div: "/",
}

# 需要括号保护的低优先级表达式（删除 not 时）
_NEEDS_PARENS = (ast.BoolOp, ast.IfExp, ast.NamedExpr, ast.Lambda)


class PythonMutationContext:
    """为算子实现提供源码坐标换算与片段读取。"""

    def __init__(self, source: str):
        self.source = source
        self.starts = line_starts(source)

    def offset(self, node: ast.AST):
        """(lineno, col_offset utf8 字节) → 字符偏移 (start, end)。"""
        s = self._abs(node.lineno, node.col_offset)
        e = self._abs(node.end_lineno, node.end_col_offset)
        return s, e

    def _abs(self, lineno: int, col_byte: int) -> int:
        line_start = self.starts[lineno - 1]
        line_end = self.starts[lineno] if lineno < len(self.starts) else len(self.source)
        line_text = self.source[line_start:line_end].rstrip("\r\n")
        try:
            char_col = len(line_text.encode("utf-8")[:col_byte].decode("utf-8"))
        except UnicodeDecodeError:
            char_col = col_byte
        return line_start + char_col

    def text(self, node: ast.AST) -> str:
        s, e = self.offset(node)
        return self.source[s:e]

    def lineno_of(self, offset: int) -> int:
        return offset_to_lineno(self.starts, offset)


def _gap_text(ctx: PythonMutationContext, left: ast.AST, right: ast.AST):
    """两个操作数节点之间的源码片段（运算符所在位置）。"""
    l_end = ctx.offset(left)[1]
    r_start = ctx.offset(right)[0]
    return l_end, r_start, ctx.source[l_end:r_start]


def _swap_symbol_in_gap(gap: str, sym: str, new_sym: str):
    pos = gap.find(sym)
    if pos < 0:
        return None
    return gap[:pos] + new_sym + gap[pos + len(sym):]


def _gen_relational(tree, ctx, out):
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        operands = [node.left, *node.comparators]
        for i, op in enumerate(node.ops):
            if type(op) not in RELATIONAL_SWAP:
                continue
            l_end, r_start, gap = _gap_text(ctx, operands[i], operands[i + 1])
            if "#" in gap or "'''" in gap or '"""' in gap:
                continue
            sym = RELATIONAL_SYMBOL[type(op)]
            new_gap = _swap_symbol_in_gap(gap, sym, RELATIONAL_SYMBOL[RELATIONAL_SWAP[type(op)]])
            if new_gap is None:
                continue
            out.append(Mutation(
                l_end, r_start, new_gap, "relational",
                f"关系运算符 {sym} → {RELATIONAL_SYMBOL[RELATIONAL_SWAP[type(op)]]}",
            ))


def _gen_arithmetic(tree, ctx, out):
    for node in ast.walk(tree):
        if not isinstance(node, ast.BinOp):
            continue
        if type(node.op) not in ARITHMETIC_SWAP:
            continue
        l_end, r_start, gap = _gap_text(ctx, node.left, node.right)
        if "#" in gap:
            continue
        sym = ARITHMETIC_SYMBOL[type(node.op)]
        new_sym = ARITHMETIC_SYMBOL[ARITHMETIC_SWAP[type(node.op)]]
        new_gap = _swap_symbol_in_gap(gap, sym, new_sym)
        if new_gap is None:
            continue
        out.append(Mutation(l_end, r_start, new_gap, "arithmetic", f"算术运算符 {sym} → {new_sym}"))


def _gen_boolean(tree, ctx, out):
    for node in ast.walk(tree):
        # 1) not X → X
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            s, e = ctx.offset(node)
            operand_text = ctx.text(node.operand)
            if isinstance(node.operand, _NEEDS_PARENS):
                operand_text = f"({operand_text})"
            out.append(Mutation(s, e, operand_text, "boolean_negation", f"移除 not: not {operand_text[:40]}"))
        # 2) True ↔ False
        elif isinstance(node, ast.Constant) and isinstance(node.value, bool):
            s, e = ctx.offset(node)
            new_lit = "False" if node.value else "True"
            out.append(Mutation(s, e, new_lit, "boolean_negation", f"布尔常量 {ctx.source[s:e]} → {new_lit}"))
        # 3) if/while 条件取反
        elif isinstance(node, (ast.If, ast.While)):
            if isinstance(node.test, (ast.UnaryOp, ast.Constant)):
                continue
            ts, te = ctx.offset(node.test)
            out.append(Mutation(ts, te, f"not ({ctx.text(node.test)})", "boolean_negation", "条件取反"))


def _gen_return_value(tree, ctx, out):
    for node in ast.walk(tree):
        if not isinstance(node, ast.Return) or node.value is None:
            continue
        if isinstance(node.value, ast.Constant) and node.value.value is None:
            continue
        vs, ve = ctx.offset(node.value)
        out.append(Mutation(vs, ve, "None", "return_value", f"返回值 {ctx.text(node.value)[:40]} → None"))


_STATEMENT_TYPES = (ast.Assign, ast.AugAssign, ast.AnnAssign, ast.Expr)
_BODY_ATTRS = ("body", "orelse", "finalbody")


def _gen_statement_deletion(tree, ctx, out):
    for node in ast.walk(tree):
        for attr in _BODY_ATTRS:
            body = getattr(node, attr, None)
            if not isinstance(body, list):
                continue
            for stmt in body:
                if not isinstance(stmt, _STATEMENT_TYPES):
                    continue
                if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
                    continue  # 文档字符串/常量表达式跳过
                s, e = ctx.offset(stmt)
                text = ctx.text(stmt).strip().splitlines()
                preview = text[0][:50] if text else ""
                if len(body) == 1:
                    out.append(Mutation(s, e, "pass", "statement_deletion", f"删除块中唯一语句: {preview}"))
                else:
                    out.append(Mutation(s, e, "", "statement_deletion", f"删除语句: {preview}"))


def _gen_boundary_value(tree, ctx, out):
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        for operand in [node.left, *node.comparators]:
            if not (isinstance(operand, ast.Constant) and isinstance(operand.value, int)):
                continue
            if isinstance(operand.value, bool):
                continue
            s, e = ctx.offset(operand)
            text = ctx.source[s:e].strip()
            if not re.fullmatch(r"\d+", text):
                continue
            out.append(Mutation(s, e, str(operand.value + 1), "boundary_value",
                                f"边界值 {operand.value} → {operand.value + 1}"))


def _gen_condition_constant(tree, ctx, out):
    for node in ast.walk(tree):
        if not isinstance(node, (ast.If, ast.IfExp)):
            continue
        if isinstance(node.test, ast.Constant):
            continue
        ts, te = ctx.offset(node.test)
        for lit in ("True", "False"):
            out.append(Mutation(ts, te, lit, "condition_constant", f"条件常量替换 → {lit}"))


def _gen_none_replacement(tree, ctx, out):
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for arg in node.args:
            if isinstance(arg, ast.Starred):
                continue
            if isinstance(arg, ast.Constant) and arg.value is None:
                continue
            s, e = ctx.offset(arg)
            out.append(Mutation(s, e, "None", "none_replacement",
                                f"调用实参 → None: {ctx.text(arg)[:40]}"))


def _gen_exception_removal(tree, ctx, out):
    for node in ast.walk(tree):
        if isinstance(node, ast.Raise):
            s, e = ctx.offset(node)
            out.append(Mutation(s, e, "pass", "exception_removal",
                                f"删除 raise: {ctx.text(node)[:50]}"))
        elif isinstance(node, ast.ExceptHandler):
            if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                s, e = ctx.offset(node.body[0])
                out.append(Mutation(s, e, "raise", "exception_removal", "吞异常 pass → 重新抛出 raise"))


def _gen_loop_condition(tree, ctx, out):
    for node in ast.walk(tree):
        if isinstance(node, ast.While):
            ts, te = ctx.offset(node.test)
            out.append(Mutation(ts, te, "False", "loop_condition", "循环条件 → False（循环体不再执行）"))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "range":
            args = node.args
            if not args or node.keywords:
                continue
            target = None
            if len(args) == 1:
                target = args[0]
            elif len(args) == 2:
                target = args[1]
            elif len(args) == 3:
                step = args[2]
                if isinstance(step, ast.Constant) and isinstance(step.value, int) and step.value > 0:
                    target = args[1]
            if target is None or isinstance(target, ast.Starred):
                continue
            s, e = ctx.offset(target)
            t = ctx.source[s:e].strip()
            if re.fullmatch(r"\d+", t):
                v = int(t) - 1
                if v >= 0:
                    out.append(Mutation(s, e, str(v), "loop_condition", f"range 上界 {t} → {v}"))
            else:
                out.append(Mutation(s, e, f"{t} - 1", "loop_condition", f"range 上界 {t} → {t} - 1"))


_GENERATORS = {
    "relational": _gen_relational,
    "arithmetic": _gen_arithmetic,
    "boolean_negation": _gen_boolean,
    "return_value": _gen_return_value,
    "statement_deletion": _gen_statement_deletion,
    "boundary_value": _gen_boundary_value,
    "condition_constant": _gen_condition_constant,
    "none_replacement": _gen_none_replacement,
    "exception_removal": _gen_exception_removal,
    "loop_condition": _gen_loop_condition,
}


class PythonMutator(Mutator):
    """基于 AST 的 Python 变异器。"""

    language = "python"
    file_exts = (".py",)

    def generate_for_file(self, rel_path: str, source: str, operators: list) -> list:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return []  # 无法解析的文件跳过
        ctx = PythonMutationContext(source)
        mutations = []
        for op in operators:
            gen = _GENERATORS.get(op)
            if gen:
                gen(tree, ctx, mutations)
            custom = custom_python_operators().get(op)
            if custom:
                for node in ast.walk(tree):
                    try:
                        mutations.extend(custom(node, ctx))
                    except Exception:
                        continue  # 插件算子异常不阻断内置算子
        specs, seen = [], set()
        starts = ctx.starts
        for m in mutations:
            if m.start < 0 or m.end > len(source) or m.start >= m.end:
                continue
            key = (m.start, m.end, m.replacement)
            if key in seen:
                continue
            seen.add(key)
            patched = source[:m.start] + m.replacement + source[m.end:]
            try:
                ast.parse(patched)
            except SyntaxError:
                continue  # 变异导致语法错误则丢弃
            specs.append(MutantSpec(
                path=rel_path,
                start_offset=m.start,
                end_offset=m.end,
                lineno=offset_to_lineno(starts, m.start),
                operator=m.operator,
                original=source[m.start:m.end],
                mutated=m.replacement,
                description=m.description,
                engine="ast",
            ))
        return specs
