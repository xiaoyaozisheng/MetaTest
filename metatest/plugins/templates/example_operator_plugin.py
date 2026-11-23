"""MetaTest 插件模板：新增一个 Python 变异算子（PRD FR-10 / 验收标准）。

使用方法：
    1. 复制本文件到任意目录：cp example_operator_plugin.py my_plugins/
    2. 运行：metatest run --plugin-dir my_plugins
       或在 metatest.yaml 中配置：
           plugins:
             dirs: ["my_plugins"]
    3. 在 mutation.operators 白名单中加入新算子名 "zero_constant"。

插件契约：模块提供 register(ctx)；ctx 提供：
    ctx.register_python_operator(name, fn)   注册 Python 变异算子
    ctx.register_c_operator(name, fn)        注册 C 变异算子（tree-sitter 后端）
    ctx.register_adapter(name, cls)          注册语言适配器

算子函数签名：fn(node, ctx) -> list[Mutation]
    node : ast.AST（Python）或 tree-sitter 节点（C）
    ctx  : metatest.mutators.python_mutator.PythonMutationContext
           - ctx.offset(node) -> (start, end) 字符偏移
           - ctx.text(node)   -> 源码片段
           - ctx.source       -> 完整源码文本
"""

import ast

from metatest.mutators.base import Mutation

OPERATOR_NAME = "zero_constant"


def gen_zero_constant(node, ctx):
    """变异算子：整数常量 0 → 1。

    与内置 boundary_value（比较边界 +1）互补：本算子覆盖赋值、默认参数、
    下标等位置的 0 常量，用于检验测试对"零值路径"的断言强度。
    """
    if not isinstance(node, ast.Constant):
        return []
    if isinstance(node.value, bool) or node.value != 0:
        return []
    if not isinstance(node.value, int):
        return []
    start, end = ctx.offset(node)
    return [Mutation(start, end, "1", OPERATOR_NAME, "整数常量 0 → 1")]


def register(ctx):
    ctx.register_python_operator(OPERATOR_NAME, gen_zero_constant)
