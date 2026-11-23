"""变异策略注册表（统一入口：按语言自动选择最佳可用变异策略）。

策略链（语言 → 优先级降序）：
  python : [ast]
  c      : [llvm_ir → tree_sitter → fallback]
  规则化 : [rule]（mutation.rule_files 指定时，适配任意语言 —— universalmutator 思路）

llvm_ir 为外部插件插槽（Mull / muti 类 IR 级引擎）：插件通过
`register_mutation_strategy("c", "llvm_ir", factory)` 注册后自动进入链首；
未注册时链会跳过并在报告中记录原因。
"""

from __future__ import annotations

from pathlib import Path

from metatest.errors import MutationError
from metatest.mutators.base import Mutation, Mutator, MutantSpec, apply_spec  # noqa: F401
from metatest.mutators.base import register_c_operator, register_python_operator  # noqa: F401

# ---------------------------------------------------------------------------
# 外部策略注册（插件插槽，PRD FR-04 预留 LLVM IR 接口的落点）
# ---------------------------------------------------------------------------

_STRATEGY_CHAINS = {
    "python": [("ast", "内置 AST 变异器")],
    "c": [
        ("llvm_ir", "LLVM IR 级变异（Mull/muti 类，需外部插件注册）"),
        ("tree_sitter", "tree-sitter AST 变异"),
        ("fallback", "词法级回退（可信度低于 AST 级）"),
    ],
    "command": [],
}

_custom_mutators: dict = {}  # (language, name) -> factory() -> Mutator


def register_mutation_strategy(language: str, name: str, factory) -> None:
    """注册外部变异策略（供插件调用，如 LLVM IR 引擎适配 Mull）。"""
    if not callable(factory):
        raise MutationError(f"变异策略 {language}/{name} 注册失败：factory 必须可调用")
    _custom_mutators[(language, name)] = factory


def registered_strategies() -> dict:
    return {f"{lang}/{name}": "external" for (lang, name) in _custom_mutators}


def get_mutator(language: str):
    """按语言返回内置变异器实例（旧接口，保留兼容）。"""
    if language == "python":
        from metatest.mutators.python_mutator import PythonMutator

        return PythonMutator()
    if language == "c":
        from metatest.mutators.c_mutator import CMutator

        return CMutator()
    return None


# ---------------------------------------------------------------------------
# 策略解析
# ---------------------------------------------------------------------------


def resolve_mutator(config, project_root) -> tuple:
    """返回 (mutator, info)；info 记录选择链与跳过原因（进报告）。"""
    # 1) 规则文件 → 规则化变异器（任意语言）
    if config.mutation.rule_files:
        if not config.source_roots or not config.mutation.include_globs:
            raise MutationError(
                "规则化变异需同时配置 source_roots（被变异目录）与 mutation.include_globs"
                "（如 [\"src/**/*.go\"]），避免误收集构建产物"
            )
        from metatest.mutators.rule_mutator import RuleMutator, load_rule_files

        rules = load_rule_files(config.mutation.rule_files, base_dir=project_root)
        if not rules:
            raise MutationError("规则文件中没有任何有效规则（需 rules[].operator/swaps）")
        info = {
            "strategy": "rule",
            "rules": len(rules),
            "rule_files": [str(p) for p in config.mutation.rule_files],
            "chain": [("rule", "规则化变异器（用户规则文件）", "chosen")],
        }
        return RuleMutator(rules), info

    language = config.language
    if language not in _STRATEGY_CHAINS:
        return None, {"strategy": "none", "chain": []}

    requested = getattr(config.mutation, "strategy", "auto")
    # 兼容旧配置键：adapter.c_parser 显式指定时视同策略请求
    if requested == "auto" and language == "c":
        c_parser = config.adapter.get("c_parser", "auto")
        if c_parser in ("tree_sitter", "fallback", "llvm_ir"):
            requested = c_parser

    chain = list(_STRATEGY_CHAINS[language])
    strict = requested != "auto"
    if strict:
        chain = [(n, d) for (n, d) in chain if n == requested]
        if not chain:
            raise MutationError(
                f"未知变异策略 {requested!r}（语言 {language} 可用: "
                f"{', '.join(n for n, _ in _STRATEGY_CHAINS[language])}）"
            )

    info = {"strategy": requested, "chain": []}
    skipped = []
    for name, desc in chain:
        if name == "llvm_ir":
            factory = _custom_mutators.get((language, name))
            if factory is None:
                skipped.append((name, "外部策略未注册（如需 IR 级变异请安装/编写插件）"))
                if strict:
                    raise MutationError(
                        "变异策略 llvm_ir 需要 IR 级引擎插件（Mull/muti 适配）注册后才能使用；"
                        "未检测到已注册插件"
                    )
                continue
            mutator = factory()
            info["chain"].append((name, desc, "chosen"))
            info["strategy"] = name
            return mutator, info
        if name == "tree_sitter":
            try:
                from metatest.mutators.c_mutator import CMutator

                mutator = CMutator(backend="tree_sitter")
            except Exception as e:
                if strict:
                    raise MutationError(
                        f"变异策略 tree_sitter 被显式指定但依赖不可用: {e}"
                        f"（请 pip install \"metatest[c]\"，或改用 auto/fallback）"
                    )
                skipped.append((name, f"tree-sitter 依赖不可用: {e}"))
                continue
            info["chain"].append((name, desc, "chosen"))
            info["strategy"] = name
            return mutator, info
        if name == "fallback":
            from metatest.mutators.c_mutator import CMutator

            mutator = CMutator(backend="fallback")
            info["chain"].append((name, desc, "chosen"))
            info["strategy"] = name
            if not strict:
                import logging

                logging.getLogger("metatest").warning(
                    "C 变异回退到词法级引擎（tree-sitter 不可用）；"
                    "建议 pip install \"metatest[c]\"。分引擎统计见报告 engine_scores。"
                )
            return mutator, info
        if name == "ast":
            from metatest.mutators.python_mutator import PythonMutator

            info["chain"].append((name, desc, "chosen"))
            info["strategy"] = name
            return PythonMutator(), info

    info["skipped"] = skipped
    return None, info
