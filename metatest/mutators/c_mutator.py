"""C 变异器（PRD FR-04）。

MVP 选型 tree-sitter（Clang AST 精度更高但依赖 LLVM 工具链；tree-sitter 纯
Python 可用、跨平台）。同时内置一个无第三方依赖的词法级回退后端，保证未安装
tree-sitter 的环境仍可做基础变异。

算子语义与 Python 共享（见 metatest/config.py OPERATORS）；
exception_removal 仅适用于有异常机制的语言，C 后端不生成该算子。
"""

from __future__ import annotations

import re

from metatest.mutators.base import (
    Mutation,
    Mutator,
    MutantSpec,
    custom_c_operators,
    line_starts,
    offset_to_lineno,
)

RELATIONAL_SWAP = {"<": "<=", "<=": "<", ">": ">=", ">=": ">", "==": "!=", "!=": "=="}
ARITHMETIC_SWAP = {"+": "-", "-": "+", "*": "/", "/": "*"}
LOGICAL_SWAP = {"&&": "||", "||": "&&"}

_REL_SYMBOLS = set(RELATIONAL_SWAP)
_ARITH_SYMBOLS = set(ARITHMETIC_SWAP)


class ByteMap:
    """utf-8 字节偏移 → 字符偏移映射（tree-sitter 使用字节偏移）。"""

    def __init__(self, text: str):
        data = text.encode("utf-8")
        mapping = [0] * (len(data) + 1)
        ci = 0
        for bi in range(len(data)):
            mapping[bi] = ci
            if (data[bi] & 0xC0) != 0x80:  # 非 UTF-8 续字节 → 字符前进
                ci += 1
        mapping[len(data)] = ci
        self.mapping = mapping

    def to_char(self, byte_offset: int) -> int:
        if byte_offset < 0:
            return 0
        if byte_offset >= len(self.mapping):
            return self.mapping[-1]
        return self.mapping[byte_offset]


class CMutationContext:
    def __init__(self, text: str, bmap: ByteMap):
        self.text = text
        self.bmap = bmap
        self.starts = line_starts(text)

    def node_text(self, node) -> str:
        return self.text[self.char_range(node)[0]:self.char_range(node)[1]]

    def char_range(self, node):
        return self.bmap.to_char(node.start_byte), self.bmap.to_char(node.end_byte)


# ---------------------------------------------------------------------------
# tree-sitter 后端
# ---------------------------------------------------------------------------


def _find_op_token(node, symbols):
    """在二元表达式子节点中找运算符 token。"""
    left = node.child_by_field_name("left")
    right = node.child_by_field_name("right")
    ids = set()
    for f in (left, right):
        if f is not None:
            ids.add(f.id)
    for child in node.children:
        if child.id in ids:
            continue
        if child.type in symbols and child.start_byte != child.end_byte:
            return child
    return None


def _mutate_binary(tree, ctx, out, symbols, swap, op_name, desc_fmt):
    for node in _walk(tree.root_node):
        if node.type != "binary_expression":
            continue
        tok = _find_op_token(node, symbols)
        if tok is None:
            continue
        sym = ctx.node_text(tok)
        new_sym = swap.get(sym)
        if not new_sym:
            continue
        s, e = ctx.char_range(tok)
        out.append(Mutation(s, e, new_sym, op_name, desc_fmt.format(sym=sym, new=new_sym)))


def _gen_relational_ts(tree, ctx, out):
    _mutate_binary(tree, ctx, out, _REL_SYMBOLS, RELATIONAL_SWAP, "relational", "关系运算符 {sym} → {new}")


def _gen_arithmetic_ts(tree, ctx, out):
    _mutate_binary(tree, ctx, out, _ARITH_SYMBOLS, ARITHMETIC_SWAP, "arithmetic", "算术运算符 {sym} → {new}")


def _gen_boolean_ts(tree, ctx, out):
    _mutate_binary(tree, ctx, out, set(LOGICAL_SWAP), LOGICAL_SWAP, "boolean_negation", "逻辑运算符 {sym} → {new}")
    for node in _walk(tree.root_node):
        if node.type != "unary_expression":
            continue
        op = node.child_by_field_name("operator")
        arg = node.child_by_field_name("argument")
        if op is None or arg is None or ctx.node_text(op) != "!":
            continue
        os_, oe = ctx.char_range(op)
        out.append(Mutation(os_, oe, "", "boolean_negation", f"移除取反 !{ctx.node_text(arg)[:40]}"))


def _enclosing_function_type(node):
    cur = node.parent
    while cur is not None:
        if cur.type == "function_definition":
            t = cur.child_by_field_name("type")
            return ctx_text_of(cur, t) if t is not None else ""
        cur = cur.parent
    return ""


def ctx_text_of(root, node):
    return root.text[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _gen_return_value_ts(tree, ctx, out):
    for node in _walk(tree.root_node):
        if node.type != "return_statement":
            continue
        expr = None
        for child in node.children:
            if child.type == ";" or child.type == "return":
                continue
            expr = child
        if expr is None:
            continue  # void return
        ret_type = _enclosing_function_type(node)
        low = ret_type.lower()
        if "void" in low or "struct" in low or "union" in low:
            continue
        s, e = ctx.char_range(expr)
        out.append(Mutation(s, e, "0", "return_value", f"返回值 {ctx.node_text(expr)[:40]} → 0"))


def _gen_statement_deletion_ts(tree, ctx, out):
    for node in _walk(tree.root_node):
        if node.type != "expression_statement":
            continue
        expr = node.child_by_field_name("expression") if hasattr(node, "child_by_field_name") else None
        if expr is None:
            named = [c for c in node.children if c.is_named and c.type != ";"]
            expr = named[0] if named else None
        if expr is None:
            continue
        if expr.type not in ("assignment_expression", "augmented_assignment_expression", "call_expression"):
            continue
        s, e = ctx.char_range(node)
        out.append(Mutation(s, e, ";", "statement_deletion", f"删除语句: {ctx.node_text(node).strip()[:50]}"))


def _gen_boundary_value_ts(tree, ctx, out):
    for node in _walk(tree.root_node):
        if node.type != "binary_expression":
            continue
        op_tok = _find_op_token(node, _REL_SYMBOLS)
        if op_tok is None:
            continue
        for field_name in ("left", "right"):
            operand = node.child_by_field_name(field_name)
            if operand is None or operand.type != "number_literal":
                continue
            text = ctx.node_text(operand).strip()
            if not re.fullmatch(r"\d+", text):
                continue
            v = int(text)
            s, e = ctx.char_range(operand)
            out.append(Mutation(s, e, str(v + 1), "boundary_value", f"边界值 {v} → {v + 1}"))


def _paren_condition(node, field_name):
    return node.child_by_field_name(field_name)


def _gen_condition_constant_ts(tree, ctx, out):
    for node in _walk(tree.root_node):
        if node.type != "if_statement":
            continue
        cond = _paren_condition(node, "condition")
        if cond is None:
            continue
        s, e = ctx.char_range(cond)
        for lit in ("0", "1"):
            out.append(Mutation(s, e, f"({lit})", "condition_constant", f"条件常量替换 → {lit}"))


def _gen_loop_condition_ts(tree, ctx, out):
    for node in _walk(tree.root_node):
        if node.type in ("while_statement", "do_while_statement"):
            cond = node.child_by_field_name("condition")
            if cond is None:
                continue
            s, e = ctx.char_range(cond)
            out.append(Mutation(s, e, "(0)", "loop_condition", "循环条件 → 0"))
        elif node.type == "for_statement":
            cond = node.child_by_field_name("condition")
            if cond is None:
                continue
            s, e = ctx.char_range(cond)
            out.append(Mutation(s, e, "0", "loop_condition", "for 循环条件 → 0"))


def _gen_none_replacement_ts(tree, ctx, out):
    use_null = "NULL" in ctx.text
    for node in _walk(tree.root_node):
        if node.type != "call_expression":
            continue
        args = node.child_by_field_name("arguments")
        if args is None:
            continue
        for arg in args.children:
            if not arg.is_named or arg.type in ("(", ")", ","):
                continue
            if arg.type in ("number_literal", "char_literal", "string_literal", "null"):
                continue
            # 仅替换标识符/成员访问类实参，降低编译失败噪声
            if arg.type not in ("identifier", "field_expression"):
                continue
            s, e = ctx.char_range(arg)
            repl = "NULL" if use_null else "0"
            out.append(Mutation(s, e, repl, "none_replacement",
                                f"实参 {ctx.node_text(arg)[:40]} → {repl}"))


def _walk(root):
    """深度优先遍历 tree-sitter 节点。"""
    stack = [root]
    while stack:
        node = stack.pop()
        yield node
        stack.extend(reversed(node.children))


_TS_GENERATORS = {
    "relational": _gen_relational_ts,
    "arithmetic": _gen_arithmetic_ts,
    "boolean_negation": _gen_boolean_ts,
    "return_value": _gen_return_value_ts,
    "statement_deletion": _gen_statement_deletion_ts,
    "boundary_value": _gen_boundary_value_ts,
    "condition_constant": _gen_condition_constant_ts,
    "none_replacement": _gen_none_replacement_ts,
    "loop_condition": _gen_loop_condition_ts,
    # exception_removal：C 无异常机制，不生成
}


# ---------------------------------------------------------------------------
# 无依赖回退后端（词法级，保守策略）
# ---------------------------------------------------------------------------


def _mask_comments_and_strings(text: str) -> str:
    chars = list(text)
    # 先屏蔽预处理器指令行（#include <...> 中的 <> 会被误判为运算符）
    for line_match in re.finditer(r"(?m)^[ \t]*#[^\n]*", text):
        for k in range(line_match.start(), line_match.end()):
            if chars[k] != "\n":
                chars[k] = " "
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            j = text.find("\n", i)
            j = n if j < 0 else j
            for k in range(i, j):
                chars[k] = " "
            i = j
        elif c == "/" and i + 1 < n and text[i + 1] == "*":
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


def _boundary_ok(prev, nxt):
    prev_ok = prev.isalnum() or prev in ")]"
    nxt_ok = nxt.isalnum() or nxt == "("
    return prev_ok and nxt_ok


def _match_paren(masked, open_idx):
    """返回与 open_idx 匹配的闭括号下标。"""
    depth = 0
    for j in range(open_idx, len(masked)):
        if masked[j] == "(":
            depth += 1
        elif masked[j] == ")":
            depth -= 1
            if depth == 0:
                return j
    return -1


def _gen_operators_fallback(source, ctx, out, operators):
    masked = _mask_comments_and_strings(source)
    two_char = {"<=": "<", ">=": ">", "==": "!=", "!=": "==", "&&": "||", "||": "&&"}
    one_char = {"<": "<=", ">": ">=", "+": "-", "-": "+"}
    n = len(masked)
    i = 0
    while i < n:
        two = masked[i:i + 2]
        one = masked[i]
        if two in two_char and _boundary_ok(_prev_nonspace(masked, i), _next_nonspace(masked, i + 1)):
            op = "boolean_negation" if two in ("&&", "||") else "relational"
            out.append(Mutation(i, i + 2, two_char[two], op, f"运算符 {two} → {two_char[two]}"))
            i += 2
            continue
        if one in one_char and _boundary_ok(_prev_nonspace(masked, i), _next_nonspace(masked, i)):
            # 排除 ->、- 数字负号前缀（负号前应是运算符/括号，这里保守跳过）
            if one == "-" and (masked[i + 1:i + 2] == ">" or masked[i + 1:i + 2] == "="):
                i += 1
                continue
            out.append(Mutation(i, i + 1, one_char[one], "arithmetic" if one in "+-" else "relational",
                                f"运算符 {one} → {one_char[one]}"))
        elif one == "!" and masked[i + 1:i + 2] != "=" and _next_nonspace(masked, i).isalnum():
            out.append(Mutation(i, i + 1, "", "boolean_negation", "移除取反 !"))
        i += 1

    # 边界值：比较运算符旁的十进制整数
    for m in re.finditer(r"(==|!=|<=|>=|<|>)\s*(-?\d+)", masked):
        num_start = m.start(2)
        num_end = m.end(2)
        after = masked[num_end:num_end + 1]
        if after and (after.isalnum() or after in "._"):
            continue  # 16 进制/后缀/浮点跳过
        try:
            v = int(m.group(2))
        except ValueError:
            continue
        out.append(Mutation(num_start, num_end, str(v + 1), "boundary_value", f"边界值 {v} → {v + 1}"))

    # 条件常量 / 循环条件
    for m in re.finditer(r"\b(if|while)\s*\(", masked):
        close = _match_paren(masked, m.end() - 1)
        if close < 0:
            continue
        inner_start, inner_end = m.end(), close
        if not masked[inner_start:inner_end].strip():
            continue
        if m.group(1) == "if":
            out.append(Mutation(inner_start, inner_end, "0", "condition_constant", "条件常量替换 → 0"))
            out.append(Mutation(inner_start, inner_end, "1", "condition_constant", "条件常量替换 → 1"))
        else:
            out.append(Mutation(inner_start, inner_end, "0", "loop_condition", "循环条件 → 0"))

    # for 循环：条件段（两个分号之间）→ 0
    for m in re.finditer(r"\bfor\s*\(", masked):
        close = _match_paren(masked, m.end() - 1)
        if close < 0:
            continue
        depth = 0
        semis = []
        for j in range(m.end(), close):
            if masked[j] == "(":
                depth += 1
            elif masked[j] == ")":
                depth -= 1
            elif masked[j] == ";" and depth == 0:
                semis.append(j)
        if len(semis) >= 2:
            cond_start, cond_end = semis[0] + 1, semis[1]
            if masked[cond_start:cond_end].strip():
                out.append(Mutation(cond_start, cond_end, "0", "loop_condition", "for 循环条件 → 0"))

    # return 值替换
    for m in re.finditer(r"\breturn\b\s*([^;{}]+);", masked):
        expr_start = m.start(1)
        expr_end = m.end(1)
        if not masked[expr_start:expr_end].strip():
            continue
        out.append(Mutation(expr_start, expr_end, "0", "return_value", "返回值 → 0"))


# ---------------------------------------------------------------------------


class CMutator(Mutator):
    """C 变异器：tree-sitter 后端优先，无依赖时回退词法级方案。"""

    language = "c"
    file_exts = (".c", ".h")

    def __init__(self, backend: str = "auto"):
        self.backend_name = backend
        self._ts = None
        if backend in ("auto", "tree_sitter"):
            try:
                import tree_sitter
                import tree_sitter_c
                from tree_sitter import Language, Parser

                self._lang = Language(tree_sitter_c.language())
                self._parser = Parser(self._lang)
                self._ts = True
            except Exception:
                self._ts = False
                if backend == "tree_sitter":
                    raise
        else:
            self._ts = False

    @property
    def backend(self) -> str:
        return "tree_sitter" if self._ts else "fallback"

    def generate_for_file(self, rel_path: str, source: str, operators: list) -> list:
        mutations = []
        if self._ts:
            data = source.encode("utf-8")
            tree = self._parser.parse(data)
            ctx = CMutationContext(source, ByteMap(source))
            for op in operators:
                gen = _TS_GENERATORS.get(op)
                if gen:
                    gen(tree, ctx, mutations)
                custom = custom_c_operators().get(op)
                if custom:
                    for node in _walk(tree.root_node):
                        try:
                            mutations.extend(custom(node, ctx))
                        except Exception:
                            continue
        else:
            ctx = CMutationContext(source, ByteMap(source))
            _gen_operators_fallback(source, ctx, mutations, operators)
        return self._finalize(rel_path, source, ctx, mutations)

    def _finalize(self, rel_path, source, ctx, mutations) -> list:
        backend_tag = "tree_sitter" if self._ts else "fallback"
        specs, seen = [], set()
        for m in mutations:
            if m.start < 0 or m.end > len(source) or m.start >= m.end:
                continue
            if source[m.start:m.end] == m.replacement:
                continue
            key = (m.start, m.end, m.replacement)
            if key in seen:
                continue
            seen.add(key)
            specs.append(MutantSpec(
                path=rel_path,
                start_offset=m.start,
                end_offset=m.end,
                lineno=offset_to_lineno(ctx.starts, m.start),
                operator=m.operator,
                original=source[m.start:m.end],
                mutated=m.replacement,
                description=m.description,
                engine=backend_tag,
            ))
        specs.sort(key=lambda s: (s.start_offset, s.end_offset))
        return specs
