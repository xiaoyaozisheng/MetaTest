"""测试质量分析（PRD FR-07）。

* Flaky 检测：同一测试重复运行，统计不稳定率
* 弱断言检测：只执行不断言、断言常量、断言相同表达式
* 重复测试检测：归一化 AST 相似度识别
* 覆盖率与变异得分结合：标记"高覆盖率低变异得分"文件
"""

from __future__ import annotations

import ast
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from metatest.adapters.base import BaseAdapter
from metatest.config import ProjectConfig
from metatest.junit import parse_junit
from metatest.models import FlakyTest, QualityReport, WeakAssertion
from metatest.mutators.base import read_source


# ---------------------------------------------------------------------------
# Flaky 检测
# ---------------------------------------------------------------------------


def detect_flaky(config: ProjectConfig, project_root, adapter: BaseAdapter,
                 runs: int | None = None, progress=None, isolate: bool = False) -> list:
    """同一测试重复运行 N 次，统计不稳定率。

    isolate=True（flakeguard 式第二阶段）：对被标记的 flaky 测试单独复跑，
    区分"孤立 flaky"（单测复跑仍不稳定）与"顺序依赖"（单测恒过 → 套件内
    状态/顺序污染）。仅 Python/pytest 支持隔离阶段。
    """
    from metatest.core.sandbox import Sandbox

    runs = runs or config.flaky.runs
    progress = progress or (lambda msg: print(msg, flush=True))
    histories: dict = {}   # test_id -> ["passed"/"failed"/"error"/"skipped", ...]
    run_summaries = []

    for i in range(runs):
        with Sandbox.create(project_root, config.sandbox.copy_exclude) as sb:
            run = adapter.run_tests(sb.path, config.timeout_sec)
            if run.junit_path:
                try:
                    summary = parse_junit(Path(sb.path) / run.junit_path)
                    for case in summary.cases:
                        histories.setdefault(case.test_id, []).append(case.status)
                    run_summaries.append(f"run{i + 1}: {summary.tests} tests, "
                                         f"{summary.failures} failures, {summary.skipped} skipped")
                except ValueError:
                    run_summaries.append(f"run{i + 1}: 无可用 JUnit 结果（outcome={run.outcome.value}）")
            else:
                run_summaries.append(f"run{i + 1}: 结果按退出码判定（exit={run.exit_code}），"
                                     "无用例级明细，无法做 per-test flaky 分析")
        progress(f"[flaky {i + 1}/{runs}] {run_summaries[-1]}")

    flaky_list = []
    for test_id, statuses in sorted(histories.items()):
        outcomes = [s for s in statuses if s in ("passed", "failed", "error")]
        if not outcomes:
            continue
        distinct = set(outcomes)
        majority = "passed" if outcomes.count("passed") >= len(outcomes) - outcomes.count("passed") else "failed"
        differing = sum(1 for s in outcomes if s != majority)
        unstable_rate = differing / len(outcomes) if outcomes else 0.0
        missing = len(statuses) - len(outcomes)
        is_flaky = len(distinct) > 1 or (missing > 0 and runs > 1)
        if is_flaky:
            flaky_list.append(FlakyTest(
                test_id=test_id,
                runs=len(statuses),
                passed=statuses.count("passed"),
                failed=statuses.count("failed") + statuses.count("error"),
                unstable_rate=unstable_rate if unstable_rate else missing / max(1, len(statuses)),
                is_flaky=True,
            ))

    # 第二阶段（flakeguard 借鉴）：隔离复测分类
    if isolate and flaky_list and config.language == "python":
        _classify_isolation(config, project_root, adapter, flaky_list,
                            min(runs, 3), progress)
    return flaky_list


def _classify_isolation(config, project_root, adapter, flaky_list, runs, progress) -> None:
    """对每个 flaky 测试单独复跑 runs 次，分类孤立 flaky vs 顺序依赖。"""
    from metatest.core.sandbox import Sandbox

    progress(f"[flaky-isolate] 对 {len(flaky_list)} 个 flaky 测试单独复跑 {runs} 次…")
    for f in flaky_list:
        node_id = _junit_id_to_node_id(f.test_id)
        if node_id is None:
            f.mode = "suite_flaky"
            continue
        outcomes = []
        for _ in range(runs):
            with Sandbox.create(project_root, config.sandbox.copy_exclude) as sb:
                run = adapter.run_tests(sb.path, config.timeout_sec, test_ids=[node_id])
                outcomes.append("passed" if run.outcome.value in ("pass", "pass_with_skips") else "failed")
        distinct = set(outcomes)
        if len(distinct) > 1:
            f.mode = "isolated_flaky"
            progress(f"[flaky-isolate] {f.test_id}: 单独运行仍不稳定 → isolated_flaky")
        elif outcomes and outcomes[0] == "failed":
            f.mode = "isolated_failing"
            progress(f"[flaky-isolate] {f.test_id}: 单独运行恒失败 → isolated_failing")
        else:
            f.mode = "order_dependent"
            progress(f"[flaky-isolate] {f.test_id}: 单独运行恒通过 → order_dependent（套件内顺序/状态依赖）")


def _junit_id_to_node_id(test_id: str):
    """pytest junit 的 classname.name → 可执行的 pytest node id；无法转换返回 None。"""
    if "." not in test_id:
        return None
    module_path, _, name = test_id.rpartition(".")
    if not module_path:
        return None
    return f"{module_path.replace('.', '/')}.py::{name}"


# ---------------------------------------------------------------------------
# 弱断言检测（静态 AST 分析）
# ---------------------------------------------------------------------------


def find_weak_assertions(project_root, test_roots) -> list:
    root = Path(project_root)
    results = []
    files = _python_test_files(root, test_roots)
    for rel, abs_path in files.items():
        try:
            source = read_source(abs_path)
            tree = compile(source, str(abs_path), "exec", ast.PyCF_ONLY_AST)
        except (OSError, UnicodeError, SyntaxError):
            continue
        import ast as ast_mod

        for node in ast_mod.walk(tree):
            if not isinstance(node, (ast_mod.FunctionDef, ast_mod.AsyncFunctionDef)):
                continue
            if not node.name.startswith("test"):
                continue
            _check_weak_test(rel, source, node, results)
    return results


def _check_weak_test(rel, source, node, results):
    import ast as ast_mod

    # 无条件跳过的测试也是"零断言"风险
    skipped = False
    for dec in node.decorator_list:
        dumped = ast_mod.dump(dec)
        if "skip" in dumped and "skipif" not in dumped:
            skipped = True

    assert_stmts = [n for n in ast_mod.walk(node) if isinstance(n, ast_mod.Assert)]
    assert_call_count = 0
    has_raises = False
    for n in ast_mod.walk(node):
        if isinstance(n, ast_mod.Call):
            f = n.func
            name = ""
            if isinstance(f, ast_mod.Attribute):
                name = f.attr
            elif isinstance(f, ast_mod.Name):
                name = f.id
            if name.startswith("assert") or name == "fail":
                assert_call_count += 1
            elif name == "raises":
                has_raises = True

    trivial = None  # (lineno, reason, snippet)
    for a in assert_stmts:
        t = a.test
        if isinstance(t, ast_mod.Constant) and t.value is True:
            trivial = (a.lineno, "trivial_assert", _src_snippet(source, a))
            break
        if isinstance(t, ast_mod.Compare) and len(t.comparators) == 1 and _same_expr(source, t.left, t.comparators[0]):
            trivial = (a.lineno, "trivial_assert", _src_snippet(source, a))
            break
        if isinstance(t, ast_mod.Constant) and not isinstance(t.value, bool):
            trivial = (a.lineno, "constant_assert", _src_snippet(source, a))
            break

    total_assertions = len(assert_stmts) + assert_call_count + (1 if has_raises else 0)
    if total_assertions == 0:
        reason = "test_skipped" if skipped else "no_assertion"
        results.append(WeakAssertion(rel, node.name, node.lineno, reason))
    elif trivial:
        results.append(WeakAssertion(rel, node.name, trivial[0], trivial[1]))


def _src_snippet(source, node) -> str:
    try:
        return source.splitlines()[node.lineno - 1].strip()[:60]
    except IndexError:
        return ""


def _same_expr(source, left, right) -> bool:
    """assert x == x 之类的自比较断言。"""
    try:
        return ast.dump(left) == ast.dump(right)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# 重复测试检测
# ---------------------------------------------------------------------------


def find_duplicate_tests(project_root, test_roots) -> list:
    """归一化函数体哈希 → 相同实现的测试用例组。"""
    import ast as ast_mod
    import hashlib

    root = Path(project_root)
    files = _python_test_files(root, test_roots)
    groups: dict = {}
    for rel, abs_path in files.items():
        try:
            source = read_source(abs_path)
            tree = compile(source, str(abs_path), "exec", ast.PyCF_ONLY_AST)
        except (OSError, UnicodeError, SyntaxError):
            continue
        for node in ast_mod.walk(tree):
            if not isinstance(node, (ast_mod.FunctionDef, ast_mod.AsyncFunctionDef)):
                continue
            if not node.name.startswith("test"):
                continue
            body = [s for s in node.body
                    if not (isinstance(s, ast_mod.Expr) and isinstance(s.value, ast_mod.Constant)
                            and isinstance(s.value.value, str))]
            if not body or (len(body) == 1 and isinstance(body[0], ast_mod.Pass)):
                continue
            try:
                normalized = ast_mod.dump(ast_mod.Module(body=body, type_ignores=[]))
            except Exception:
                continue
            h = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:12]
            groups.setdefault(h, []).append((rel, node.name))

    duplicates = []
    for members in groups.values():
        if len(members) > 1:
            base = members[0]
            for other in members[1:]:
                duplicates.append((base[0], base[1], other[0], other[1]))
    return duplicates


def _python_test_files(root, test_roots):
    from metatest.adapters.base import collect_files

    return collect_files(root, test_roots, (".py",))


# ---------------------------------------------------------------------------
# 覆盖率 × 变异得分（高覆盖率低变异得分标记）
# ---------------------------------------------------------------------------


def parse_coverage_xml(path) -> dict:
    """解析 cobertura 格式 coverage.xml → {相对路径: line_rate}。"""
    result = {}
    try:
        root = ET.parse(str(path)).getroot()
    except (OSError, ET.ParseError):
        return result
    for cls in root.iter("class"):
        filename = cls.get("filename")
        rate = cls.get("line-rate")
        if filename and rate:
            try:
                result[Path(filename).as_posix()] = float(rate)
            except ValueError:
                continue
    # 顶层 line-rate 兜底（按包聚合时）
    if not result:
        for pkg in root.iter("package"):
            if pkg.get("name") and pkg.get("line-rate"):
                try:
                    result[pkg.get("name")] = float(pkg.get("line-rate"))
                except ValueError:
                    continue
    return result


def combine_coverage_with_mutation(analysis, coverage: dict,
                                   coverage_threshold: float = 0.8,
                                   score_threshold: float = 0.5,
                                   min_mutants: int = 3) -> list:
    """标记"高覆盖率低变异得分"文件：测试在执行但没在验证。"""
    flagged = []
    for path, info in analysis.file_scores().items():
        cov = _match_coverage(coverage, path)
        score = info["score"]
        if cov is None or score is None or info["scored"] < min_mutants:
            continue
        if cov >= coverage_threshold and score < score_threshold:
            flagged.append({
                "file": path,
                "coverage": round(cov, 3),
                "score": round(score, 3),
                "mutants": info["scored"],
                "survived": info["survived"],
            })
    return flagged


def _match_coverage(coverage: dict, path: str):
    if path in coverage:
        return coverage[path]
    for k, v in coverage.items():
        if path.endswith(k) or k.endswith(path):
            return v
    return None


# ---------------------------------------------------------------------------
# C 测试质量分析（tree-sitter；借鉴 sixth_sense 的 test-smell 维度）
# ---------------------------------------------------------------------------

_C_ASSERT_NAMES = re.compile(
    r"^(assert|static_assert|CHECK|REQUIRE|EXPECT|TEST_ASSERT\w*|CU_ASSERT\w*|ck_assert\w*|fail)$",
    re.IGNORECASE,
)


def find_weak_assertions_c(project_root, test_roots) -> list:
    """C 测试弱断言检测：无断言 / 常量断言 / 自比较断言。

    tree-sitter 可用时走 AST（函数定义 + call_expression）；
    缺依赖时回退保守的正则扫描。
    """
    results = []
    files = _c_test_files(project_root, test_roots)
    try:
        import tree_sitter_c
        from tree_sitter import Language, Parser

        parser = Parser(Language(tree_sitter_c.language()))
    except Exception:
        parser = None
    for rel, abs_path in files.items():
        try:
            source = read_source(abs_path)
        except (OSError, UnicodeError):
            continue
        if parser is not None:
            results.extend(_c_weak_ast(rel, source, parser))
        else:
            results.extend(_c_weak_regex(rel, source))
    return results


def _c_test_files(root, test_roots):
    from metatest.adapters.base import collect_files

    return collect_files(root, test_roots, (".c",))


def _c_function_name(node, source: str):
    decl = node.child_by_field_name("declarator")
    while decl is not None and decl.type in ("function_declarator", "pointer_declarator", "parenthesized_declarator"):
        inner = decl.child_by_field_name("declarator")
        if inner is None:
            break
        decl = inner
    return source[decl.start_byte:decl.end_byte] if decl is not None else ""


def _c_weak_ast(rel: str, source: str, parser) -> list:
    data = source.encode("utf-8")
    tree = parser.parse(data)
    results = []
    for node in _ts_walk(tree.root_node):
        if node.type != "function_definition":
            continue
        name = _c_function_name(node, source)
        if not _looks_like_c_test(name, rel):
            continue
        calls = [n for n in _ts_walk(node) if n.type == "call_expression"]
        assert_calls = []
        for call in calls:
            fn = call.child_by_field_name("function")
            if fn is None:
                continue
            fname = source[fn.start_byte:fn.end_byte]
            if _C_ASSERT_NAMES.match(fname):
                args = call.child_by_field_name("arguments")
                arg_text = source[args.start_byte:args.end_byte] if args is not None else ""
                assert_calls.append((fname, arg_text, call.start_byte))
        if not assert_calls:
            results.append(WeakAssertion(rel, name, _byte_to_line(source, node.start_byte), "no_assertion"))
            continue
        for fname, arg_text, start_byte in assert_calls:
            core = arg_text.strip("() \t\r\n")
            if re.fullmatch(r"(1|true|TRUE|0\s*==\s*0|!0)", core):
                results.append(WeakAssertion(rel, name, _byte_to_line(source, start_byte),
                                             "trivial_assert"))
            elif _c_same_text(core):
                results.append(WeakAssertion(rel, name, _byte_to_line(source, start_byte),
                                             "trivial_assert"))
    return results


def _c_weak_regex(rel: str, source: str) -> list:
    """无 tree-sitter 时的保守回退：按函数块粗分。"""
    results = []
    pattern = re.compile(
        r"(?ms)^[\w\*\s]+\b(\w+)\s*\([^)]*\)\s*\{.*?\n\}")
    for m in pattern.finditer(source):
        name, body = m.group(1), m.group(0)
        if not _looks_like_c_test(name, rel):
            continue
        n_asserts = len(_C_ASSERT_NAMES.findall(body))
        if n_asserts == 0:
            results.append(WeakAssertion(rel, name, source[:m.start()].count("\n") + 1, "no_assertion"))
    return results


def _looks_like_c_test(name: str, rel: str) -> bool:
    if re.match(r"^(test|Test|TEST)", name):
        return True
    return "test" in Path(rel).name.lower() and re.match(r"^[A-Za-z_]\w*$", name or "") is not None \
        and "check" in name.lower()


def _c_same_text(arg: str) -> bool:
    m = re.fullmatch(r"(.+?)\s*==\s*\1", arg)
    return bool(m)


def _byte_to_line(source: str, byte_off: int) -> int:
    from metatest.mutators.base import line_starts, offset_to_lineno

    try:
        char_off = len(source.encode("utf-8")[:byte_off].decode("utf-8"))
    except UnicodeDecodeError:
        char_off = byte_off
    return offset_to_lineno(line_starts(source), char_off)


def _ts_walk(root):
    stack = [root]
    while stack:
        node = stack.pop()
        yield node
        stack.extend(reversed(node.children))


# ---------------------------------------------------------------------------
# 三轴质量评分（借鉴 sixth_sense：adequacy / redundancy / maintainability）
# ---------------------------------------------------------------------------


def quality_axes(analysis=None, quality=None) -> dict:
    """语言无关的三轴质量评分。

    adequacy       充分性：变异得分（有分析结果时）；无则 None
    redundancy     冗余：重复测试组数
    maintainability 可维护性：弱断言测试数（test smell）
    """
    axes = {
        "adequacy": None,
        "redundancy": 0,
        "maintainability": 0,
        "notes": [],
    }
    if quality is not None:
        axes["redundancy"] = len(quality.duplicate_tests)
        axes["maintainability"] = len(quality.weak_assertions)
    if analysis is not None and analysis.score is not None:
        axes["adequacy"] = round(analysis.score, 4)
    else:
        axes["notes"].append("无变异分析数据时 adequacy 不可计算（可先运行 metatest run）")
    if axes["redundancy"] == 0 and axes["maintainability"] == 0 and axes["adequacy"] is None:
        axes["notes"].append("三轴均无数据：请确认 test_roots 配置正确")
    return axes


# ---------------------------------------------------------------------------
# 汇总
# ---------------------------------------------------------------------------


def build_quality_report(config: ProjectConfig, project_root, adapter=None,
                         analysis=None, flaky_tests=None, run_flaky=False,
                         progress=None) -> QualityReport:
    report = QualityReport()
    if run_flaky and adapter is not None:
        report.flaky_tests = detect_flaky(config, project_root, adapter, progress=progress,
                                          isolate=config.flaky.isolate)
    if config.language == "c":
        report.weak_assertions = find_weak_assertions_c(project_root, config.test_roots)
    else:
        weak = find_weak_assertions(project_root, config.test_roots)
        report.weak_assertions = weak
    report.duplicate_tests = find_duplicate_tests(project_root, config.test_roots)
    if analysis is not None:
        cov_path = Path(project_root) / config.adapter.get("coverage_xml", "coverage.xml")
        if cov_path.exists():
            coverage = parse_coverage_xml(cov_path)
            report.high_coverage_low_mutation = combine_coverage_with_mutation(analysis, coverage)
        report.axes = quality_axes(analysis, report)
    else:
        report.axes = quality_axes(None, report)
    from metatest.models import build_suggestions

    report.suggestions = build_suggestions(analysis if analysis else None, report if report.has_findings() else None)
    return report
