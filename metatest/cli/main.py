"""MetaTest CLI（PRD FR-09：CLI 退出码 0/1/2/3）。"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from pathlib import Path

from metatest import __version__
from metatest.adapters import ADAPTER_REGISTRY, create_adapter, detect_language
from metatest.config import (
    CONFIG_FILE_NAME,
    OPERATORS,
    commands_allowed,
    load_config,
    normalize_operators,
)
from metatest.errors import ConfigError, MetaTestError
from metatest.exitcodes import EXIT_GATE, EXIT_OK, EXIT_PLATFORM, EXIT_SELFTEST
from metatest.report import write_reports
from metatest.report.json_report import analysis_from_dict

log = logging.getLogger("metatest")


# ---------------------------------------------------------------------------
# 输出工具
# ---------------------------------------------------------------------------


class Output:
    """CLI 输出：终端打印 + 可选 sink（Web 控制台用它收集实时日志）。"""

    def __init__(self, quiet: bool = False, sink=None):
        self.quiet = quiet
        self.sink = sink

    def __call__(self, msg: str) -> None:
        if not self.quiet:
            print(msg, flush=True)
        if self.sink:
            self.sink(msg)

    def important(self, msg: str) -> None:
        print(msg, flush=True)
        if self.sink:
            self.sink(msg)


# ---------------------------------------------------------------------------
# 质量门禁（PRD FR-09 退出码语义）
# ---------------------------------------------------------------------------


def evaluate_gate(cfg, analysis: AnalysisResult, quality) -> tuple:
    """返回 (gate_info, failures)；failures 非空 → 退出码 1。"""
    failures = []
    threshold = cfg.quality_gate.min_mutation_score
    score = analysis.score_percent()
    if threshold is not None:
        if score is None:
            failures.append(f"变异得分无法计算（无可计分变异体），门禁阈值 {threshold}%")
        elif score < threshold:
            failures.append(f"变异得分 {score}% 低于门禁阈值 {threshold}%")
    if cfg.quality_gate.fail_on_survived and analysis.survived > 0:
        failures.append(f"存在 {analysis.survived} 个漏测变异（fail_on_survived）")
    if quality is not None:
        if cfg.quality_gate.max_flaky is not None and len(quality.flaky_tests) > cfg.quality_gate.max_flaky:
            failures.append(f"flaky 测试 {len(quality.flaky_tests)} 个，超过上限 {cfg.quality_gate.max_flaky}")
        if cfg.quality_gate.max_weak_assertions is not None and \
                len(quality.weak_assertions) > cfg.quality_gate.max_weak_assertions:
            failures.append(
                f"弱断言测试 {len(quality.weak_assertions)} 个，超过上限 {cfg.quality_gate.max_weak_assertions}"
            )
    gate_info = {
        "threshold": threshold,
        "score": score,
        "passed": not failures,
        "failures": failures,
    }
    return gate_info, failures


# ---------------------------------------------------------------------------
# metatest run
# ---------------------------------------------------------------------------


def cmd_run(args, out: Output) -> int:
    cfg = load_config(args.config, project_root=args.project_root)
    root = cfg.resolve_root()
    if args.parallel:
        cfg.parallelism = args.parallel
    if args.timeout:
        cfg.timeout_sec = args.timeout
    if args.test_selection:
        cfg.mutation.test_selection = True
    if args.strategy:
        cfg.mutation.strategy = args.strategy
    if not commands_allowed(cfg, args.allow_commands):
        out.important(
            "安全保护：metatest.yaml 中的命令默认不执行（信任不来自仓库内容，攻击者无法随仓库提交）。\n"
            f"  确认 {cfg.config_path} 中的 build_cmd/test_cmd 可信后：\n"
            "    metatest allow                     # 登记信任（配置被改动后需重新确认）\n"
            "    metatest run --allow-commands      # 或本次一次性放行\n"
            "    METATEST_ALLOW_COMMANDS=1          # 或 CI 中显式允许\n"
            "  详见 docs/configuration.md 安全章节。"
        )
        return EXIT_PLATFORM

    from metatest.plugins import load_plugins

    load_plugins(cfg, extra_dirs=args.plugin_dir or [])

    adapter = create_adapter(cfg, root)
    adapter.prepare()

    # 算子选择（CLI 覆盖配置）
    operators = normalize_operators(args.operators.split(",")) if args.operators else cfg.effective_operators()
    if args.exclude_operators:
        excluded = set(normalize_operators(args.exclude_operators))
        operators = [o for o in operators if o not in excluded]
    out(f"[init] 项目 {cfg.name}（{cfg.language}）· 算子 {len(operators)} 个 · 并行 {cfg.parallelism}")

    specs = adapter.generate_mutants(operators)
    mutants = [s.to_mutant() for s in specs]
    out(f"[init] 生成变异体 {len(mutants)} 个")
    if adapter.mutator_info:
        chain_txt = " -> ".join(n for n, _d, _s in adapter.mutator_info.get("chain", []))
        out(f"[init] 变异策略: {adapter.mutator_info.get('strategy')}（链: {chain_txt}）")

    # 增量模式
    targets, source = None, ""
    if args.incremental or cfg.mutation.incremental:
        from metatest.core.incremental import changed_targets

        targets = changed_targets(root, args.diff_ref,
                                  args.changed_files.split(",") if args.changed_files else None)
        source = f"git diff {args.diff_ref}" if args.diff_ref else ("changed-files" if args.changed_files else "git diff HEAD")
        out(f"[incremental] 改动文件 {len(targets)} 个")

    from metatest.core.engine import MutationEngine

    engine = MutationEngine(cfg, root, adapter, progress=out)
    try:
        analysis = engine.run(
            mutants,
            incremental_targets=targets,
            incremental_source=source,
            no_cache=args.no_cache,
            equivalents_file=args.equivalents,
        )
    except MetaTestError as e:
        out.important(f"[error] {e}")
        return EXIT_PLATFORM

    # 基线失败 → 平台无法评估（退出码 2）
    from metatest.models import RunOutcome

    if analysis.baseline is None or analysis.baseline.outcome in (
        RunOutcome.FAIL, RunOutcome.ERROR, RunOutcome.TIMEOUT, RunOutcome.ALL_SKIPPED
    ):
        out.important("[error] 基线测试未通过，变异评估中止（先修复测试/环境）。")
        return EXIT_PLATFORM

    # 测试质量分析（PRD FR-07）
    quality = None
    if not args.no_quality:
        from metatest.core.quality import build_quality_report

        quality = build_quality_report(
            cfg, root, adapter=adapter, analysis=analysis,
            run_flaky=(cfg.flaky.enabled or args.flaky),
            progress=out,
        )

    # 质量门禁
    gate_info, failures = evaluate_gate(cfg, analysis, quality)

    # 报告（PRD FR-09）
    output_dir = Path(args.output_dir) if args.output_dir else root / cfg.report.output_dir
    formats = tuple(args.formats.split(",")) if args.formats else cfg.report.formats
    paths = write_reports(analysis, output_dir, config=cfg, quality=quality,
                          project_root=root, gate=gate_info, formats=formats)

    # 摘要
    score = analysis.score_percent()
    out.important("=" * 62)
    out.important(
        f"变异体 {len(analysis.mutants)} | killed {analysis.killed} | survived {analysis.survived} "
        f"| timeout {analysis.timeout} | equivalent {analysis.equivalent} | error {analysis.error}"
    )
    if score is None:
        out.important("变异得分: N/A（无可计分变异体）")
    else:
        verdict = "达标" if gate_info["passed"] else "未达标"
        out.important(f"变异得分: {score:.1f}%" + (f"（门禁阈值 {gate_info['threshold']:.0f}% → {verdict}）" if gate_info["threshold"] is not None else ""))
    engine_scores = analysis.engine_scores()
    if len(engine_scores) > 1:
        for eng, g in engine_scores.items():
            tag = "AST/AST级" if eng in ("ast", "tree_sitter") else "词法级回退（可信度注意）"
            s_txt = f"{g['score']:.1f}%" if g["score"] is not None else "N/A"
            out.important(f"  引擎 [{eng}·{tag}]: {g['total']} 个，得分 {s_txt}")
    if analysis.incremental:
        inc = analysis.incremental
        out.important(f"增量模式: {inc.get('kept', 0)}/{inc.get('total', 0)} 个变异体与改动相关")
    if analysis.test_selection:
        ts = analysis.test_selection
        out.important(f"测试关联筛选: {ts['tests']} 个测试建图（{ts['build_sec']}s），零覆盖变异体免执行")
    if failures:
        for f in failures:
            out.important(f"  ✗ {f}")
    for p in sorted(paths.values()):
        out.important(f"报告: {p}")
    out.important("=" * 62)
    return EXIT_GATE if failures else EXIT_OK


# ---------------------------------------------------------------------------
# metatest selftest
# ---------------------------------------------------------------------------


def cmd_selftest(args, out: Output) -> int:
    from metatest.selftest.runner import discover_cases, run_selftest

    cases = discover_cases(args.baseline_dir)
    if args.list:
        out(f"自检基准项目（{len(cases)} 个）：")
        for c in cases:
            out(f"  {c.case_id:28s} [{c.kind}] {c.description}")
        return EXIT_OK
    if not cases:
        out.important(f"未找到基准项目目录: {args.baseline_dir or '(内置)'}")
        return EXIT_PLATFORM
    case_filter = set(args.case) if args.case else None
    results = run_selftest(cases, progress=out, case_filter=case_filter)

    passed = sum(1 for r in results if r.passed and not r.skipped)
    skipped = sum(1 for r in results if r.skipped)
    failed = sum(1 for r in results if not r.passed and not r.skipped)
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(
            json.dumps({
                "summary": {"passed": passed, "failed": failed, "skipped": skipped},
                "results": [r.as_dict() for r in results],
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        out(f"自检 JSON: {args.json}")

    out.important("=" * 62)
    out.important(f"元测试自检: 通过 {passed} · 失败 {failed} · 跳过(环境缺失) {skipped}")
    for r in results:
        if not r.passed and not r.skipped:
            out.important(f"  ✗ {r.case_id}: expected={r.expected} actual={r.actual} {r.message}")
    rate = (passed / (passed + failed) * 100) if (passed + failed) else 0
    out.important(f"自检通过率: {rate:.0f}%（已执行用例，跳过用例不计入）")
    out.important("=" * 62)
    return EXIT_SELFTEST if failed else EXIT_OK


# ---------------------------------------------------------------------------
# metatest flaky / quality / report / plugins / ci / init
# ---------------------------------------------------------------------------


def _load_for_quality(args, out):
    cfg = load_config(args.config, project_root=args.project_root)
    if not commands_allowed(cfg, False):
        raise ConfigError("不可信配置：使用 metatest init 生成配置或设置 METATEST_ALLOW_COMMANDS=1")
    from metatest.plugins import load_plugins

    load_plugins(cfg, extra_dirs=args.plugin_dir or [])
    adapter = create_adapter(cfg, cfg.resolve_root())
    adapter.prepare()
    return cfg, adapter


def cmd_flaky(args, out: Output) -> int:
    from metatest.core.quality import detect_flaky

    cfg, adapter = _load_for_quality(args, out)
    runs = args.runs or cfg.flaky.runs
    out(f"[flaky] 重复运行 {runs} 次: {cfg.test_cmd}")
    flaky = detect_flaky(cfg, cfg.resolve_root(), adapter, runs=runs, progress=out,
                         isolate=args.isolate or cfg.flaky.isolate)
    out.important("=" * 62)
    if flaky:
        out.important(f"检测到 {len(flaky)} 个 flaky 测试：")
        for f in flaky:
            out.important(f"  ✗ {f.test_id}  通过 {f.passed}/{f.runs} 失败 {f.failed} 不稳定率 {f.unstable_rate:.0%}")
        return EXIT_GATE
    out.important(f"未检测到 flaky 测试（每个测试 {runs} 次运行结果一致）。")
    return EXIT_OK


def cmd_quality(args, out: Output) -> int:
    from metatest.core.quality import build_quality_report

    cfg, adapter = _load_for_quality(args, out)
    quality = build_quality_report(
        cfg, cfg.resolve_root(), adapter=adapter, analysis=None,
        run_flaky=args.flaky or cfg.flaky.enabled, progress=out,
    )
    out.important("=" * 62)
    out.important(f"flaky 测试: {len(quality.flaky_tests)} | 弱断言: {len(quality.weak_assertions)} "
                  f"| 重复测试: {len(quality.duplicate_tests)} 组 | 覆盖率结合: 需要 run 的 results.json")
    for w in quality.weak_assertions:
        out.important(f"  ✗ 弱断言 {w.file}:{w.lineno} {w.test} [{w.reason}]")
    for a, b, c, d in quality.duplicate_tests:
        out.important(f"  ✗ 重复 {a}::{b} ↔ {c}::{d}")
    for f in quality.flaky_tests:
        out.important(f"  ✗ flaky {f.test_id}（{f.unstable_rate:.0%}）")
    for s in quality.suggestions:
        out(f"  💡 {s}")
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(quality.as_dict(), ensure_ascii=False, indent=2),
                                   encoding="utf-8")
        out(f"质量报告 JSON: {args.json}")
    if args.strict and quality.has_findings():
        return EXIT_GATE
    return EXIT_OK


def cmd_report(args, out: Output) -> int:
    doc = json.loads(Path(args.results).read_text(encoding="utf-8"))
    analysis = analysis_from_dict(doc)
    quality = doc.get("quality")
    gate = doc.get("gate") if isinstance(doc.get("gate"), dict) else None
    out_path = Path(args.out)
    if out_path.suffix.lower() in (".html", ".xml"):
        # --out 是文件路径：直接写该文件
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if args.format == "html":
            from metatest.report.html_report import write_html_report

            paths = {"html": write_html_report(analysis, out_path, quality=quality, gate=gate,
                                               project_root=args.project_root)}
        else:
            from metatest.report.junit_report import write_junit_report

            paths = {"junit_xml": write_junit_report(analysis, out_path)}
    else:
        paths = write_reports(analysis, out_path, quality=quality, gate=gate,
                              formats=[args.format], project_root=args.project_root)
    for p in sorted(paths.values()):
        out(f"报告已生成: {p}")
    return EXIT_OK


def cmd_plugins(args, out: Output) -> int:
    from metatest.mutators.base import custom_python_operators

    if args.plugins_cmd == "template":
        src = Path(__file__).resolve().parent.parent / "plugins" / "templates" / "example_operator_plugin.py"
        dest = Path(args.dest or "example_operator_plugin.py")
        shutil.copy(src, dest)
        out(f"插件模板已复制: {dest}\n使用: metatest run --plugin-dir {dest.parent}（算子名 zero_constant）")
        return EXIT_OK

    out("内置适配器: " + ", ".join(sorted(ADAPTER_REGISTRY)))
    out(f"内置变异算子（{len(OPERATORS)} 个）:")
    for name, desc in OPERATORS.items():
        out(f"  {name:20s} {desc}")
    customs = custom_python_operators()
    if customs:
        out(f"插件算子: {', '.join(sorted(customs))}")
    cfg_path = Path("metatest.yaml")
    if cfg_path.exists():
        from metatest.plugins import load_plugins

        loaded = load_plugins(load_config(cfg_path))
        out(f"已加载插件: {loaded or '（无）'}")
    return EXIT_OK


def cmd_ci(args, out: Output) -> int:
    from metatest.cli.ci_templates import template_for

    text = template_for(args.ci)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        out(f"CI 模板已写入: {args.out}")
    else:
        print(text)
    return EXIT_OK


def _infer_python_layout(target: Path) -> dict:
    """启发式推断 Python 项目布局（确定性规则，非 AI 语义理解）。"""
    skip = {"venv", ".venv", "build", "dist", "node_modules", ".metatest", "examples", "docs"}
    test_roots = []
    for d in sorted(p for p in target.iterdir() if p.is_dir() and p.name not in skip
                    and not p.name.startswith(".")):
        py_files = list(d.glob("test_*.py")) + list(d.glob("*_test.py"))
        if py_files:
            test_roots.append(d.name)
    # 常见显式测试目录（即使暂无测试文件也采纳）
    for cand in ("tests", "test"):
        if (target / cand).exists() and cand not in test_roots:
            test_roots.insert(0, cand)
    source_roots = []
    if (target / "src").is_dir():
        source_roots = ["src"]
    else:
        for d in sorted(p for p in target.iterdir() if p.is_dir()
                        and p.name not in skip and not p.name.startswith(".")):
            if d.name in test_roots:
                continue
            if list(d.glob("__init__.py")) or list(d.glob("*.py")):
                source_roots.append(d.name)
    return {
        "test_roots": test_roots or ["tests"],
        "source_roots": source_roots or ["src"],
        "test_cmd": "python -m pytest -q",
        "inferred": bool(test_roots or source_roots),
    }


def _infer_c_layout(target: Path) -> dict:
    skip = {"build", "out", "cmake-build-debug", ".metatest"}
    c_dirs, test_dirs = [], []
    for d in sorted(p for p in target.iterdir() if p.is_dir() and p.name not in skip
                    and not p.name.startswith(".")):
        c_files = list(d.glob("*.c")) + list(d.glob("*.h"))
        tests = [f for f in c_files if "test" in f.name.lower()]
        if tests:
            test_dirs.append(d.name)
        elif c_files:
            c_dirs.append(d.name)
    if (target / "src").is_dir():
        c_dirs = ["src"]
    return {
        "test_roots": test_dirs or ["tests"],
        "source_roots": c_dirs or ["src"],
        "inferred": bool(c_dirs or test_dirs),
    }


def _apply_inference(text: str, inferred: dict) -> str:
    """把推断结果写进模板文本（保留模板注释结构）。"""
    import re

    src_list = "[" + ", ".join(f'"{r}"' for r in inferred["source_roots"]) + "]"
    test_list = "[" + ", ".join(f'"{r}"' for r in inferred["test_roots"]) + "]"
    text = re.sub(r'source_roots: \[[^\]]*\]', f'source_roots: {src_list}', text)
    text = re.sub(r'test_roots: \[[^\]]*\]', f'test_roots: {test_list}', text)
    if inferred.get("test_cmd"):
        text = re.sub(r'test_cmd: "python -m pytest -q"[^\n]*',
                      f'test_cmd: "{inferred["test_cmd"]}"', text)
    return text


def cmd_init(args, out: Output) -> int:
    from metatest.cli.init_templates import template_for

    target = Path(args.dir or ".")
    cfg_path = target / CONFIG_FILE_NAME
    if cfg_path.exists() and not args.force:
        out.important(f"已存在 {cfg_path}（--force 覆盖）")
        return EXIT_PLATFORM
    language = args.language or detect_language(target)
    text = template_for(language, target.resolve().name)
    if language == "python":
        inferred = _infer_python_layout(target)
        if inferred["inferred"]:
            text = _apply_inference(text, inferred)
            out(f"[init] 推断布局: source_roots={inferred['source_roots']} "
                f"test_roots={inferred['test_roots']}（确定性规则，可手动修正）")
    elif language == "c":
        inferred = _infer_c_layout(target)
        if inferred["inferred"]:
            text = _apply_inference(text, inferred)
            out(f"[init] 推断布局: source_roots={inferred['source_roots']} "
                f"test_roots={inferred['test_roots']}（构建命令仍需按工具链确认）")
    cfg_path.write_text(text, encoding="utf-8")
    from metatest.config import grant_trust

    grant_trust(cfg_path, target)
    out(f"已生成 {cfg_path}（语言: {language}）")
    out("信任已登记到用户级存储（~/.metatest/trusted.json，绑定配置内容指纹）——")
    out("  配置被改动后需 metatest allow 重新确认；仓库内无法自我授权。")
    out("下一步：")
    out(f"  1. 检查 {CONFIG_FILE_NAME}：确认 test_cmd / source_roots / test_roots")
    out(f"  2. metatest run            # 全量变异评估")
    out(f"  3. metatest run --incremental --diff-ref main   # PR 增量门禁")
    out(f"  4. metatest selftest       # 平台自检")
    return EXIT_OK


def cmd_allow(args, out: Output) -> int:
    """显式信任一个配置（写入用户级存储，绑定内容指纹）。"""
    from metatest.config import grant_trust, load_config

    path = Path(args.config or CONFIG_FILE_NAME)
    if not path.exists():
        out.important(f"配置不存在: {path}")
        return EXIT_PLATFORM
    cfg = load_config(path)
    grant_trust(path, args.project_root)
    out.important(f"已登记信任: {path.resolve()}")
    out.important(f"  将允许执行: build_cmd={cfg.build_cmd!r} test_cmd={cfg.test_cmd!r}")
    out.important("  配置内容被改动后信任自动失效（绑定内容指纹）。撤销: metatest deny")
    return EXIT_OK


def cmd_deny(args, out: Output) -> int:
    from metatest.config import load_config, revoke_trust

    path = Path(args.config or CONFIG_FILE_NAME)
    if revoke_trust(path, args.project_root):
        out(f"已撤销信任: {path.resolve()}")
        return EXIT_OK
    out(f"该配置未登记信任: {path.resolve()}")
    return EXIT_OK


# ---------------------------------------------------------------------------
# metatest python（解释器探测与绑定）
# ---------------------------------------------------------------------------


def cmd_python(args, out: Output) -> int:
    from metatest.adapters.python_adapter import available_interpreters
    from metatest.interp_store import assign, clear, get_assigned

    root = Path(args.project_root or (Path(args.config).parent if args.config else Path.cwd()))
    if args.set:
        try:
            assign(root, args.set)
        except FileNotFoundError as e:
            out.important(f"[python] {e}")
            return EXIT_PLATFORM
        out.important(f"已为项目绑定解释器: {Path(args.set).resolve()}（项目 {root.resolve()}）")
        return EXIT_OK
    if args.clear:
        removed = clear(root)
        out.important("已恢复自动探测" if removed else "该项目没有绑定解释器")
        return EXIT_OK

    assigned = get_assigned(root)
    out.important(f"项目: {root.resolve()}")
    out.important(f"当前使用: {assigned or '（自动探测）'}")
    rows = available_interpreters(root)
    if not rows:
        out.important("未发现任何 python 解释器")
        return EXIT_PLATFORM
    out.important("候选解释器（pytest 可用性已实测）：")
    for row in rows:
        tags = []
        if row["assigned"]:
            tags.append("已绑定")
        if row["self"]:
            tags.append("MetaTest 自身")
        tag = f"  [{' / '.join(tags)}]" if tags else ""
        out(f"  {'✓' if row['pytest'] else '✗'} {row['path']}{tag}")
    out("绑定: metatest python --set <解释器路径>   恢复自动: metatest python --clear")
    return EXIT_OK


# ---------------------------------------------------------------------------
# metatest ui（本地 Web 控制台）
# ---------------------------------------------------------------------------


def cmd_ui(args, out: Output) -> int:
    from metatest.web.launcher import _free_port
    from metatest.web.server import serve

    port = args.port or _free_port(args.host)
    return serve(
        host=args.host,
        port=port,
        open_browser=not args.no_browser,
        project=args.project,
        out=out.important,
    )


# ---------------------------------------------------------------------------
# 参数解析
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="metatest",
        description="MetaTest — 测试有效性评估与元测试平台（变异测试 + 测试质量分析 + 元测试自检）",
    )
    parser.add_argument("--version", action="version", version=f"metatest {__version__}")
    parser.add_argument("--verbose", action="store_true", help="调试日志")
    parser.add_argument("--quiet", action="store_true", help="精简输出")
    # 子命令级全局选项（SUPPRESS：未传时不覆盖根级值，两处皆可用）
    qv = argparse.ArgumentParser(add_help=False)
    qv.add_argument("--verbose", action="store_true", default=argparse.SUPPRESS, help="调试日志")
    qv.add_argument("--quiet", action="store_true", default=argparse.SUPPRESS, help="精简输出")
    sub = parser.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--config", default=None, help="metatest.yaml 路径（默认当前目录）")
        p.add_argument("--project-root", default=None, help="项目根目录（默认配置文件所在目录）")
        p.add_argument("--plugin-dir", action="append", default=[], help="插件目录（可多次）")

    p = sub.add_parser("run", parents=[qv], help="运行变异测试并生成报告（默认命令）")
    common(p)
    p.add_argument("--incremental", action="store_true", help="增量：只评估改动相关变异体")
    p.add_argument("--diff-ref", default=None, help="git diff 基准（默认 HEAD=未提交改动）")
    p.add_argument("--changed-files", default=None, help="逗号分隔的改动文件列表（无 git 场景）")
    p.add_argument("--operators", default=None, help="逗号分隔算子白名单（覆盖配置）")
    p.add_argument("--exclude-operators", default=None, help="逗号分隔算子黑名单")
    p.add_argument("--strategy", default=None,
                   help="变异策略（覆盖配置）: auto / ast / tree_sitter / fallback / llvm_ir")
    p.add_argument("--parallel", type=int, default=None, help="并行度（覆盖配置）")
    p.add_argument("--timeout", type=float, default=None, help="单变异体超时秒数（覆盖配置）")
    p.add_argument("--no-cache", action="store_true", help="禁用结果缓存")
    p.add_argument("--test-selection", action="store_true",
                   help="测试关联筛选：只运行覆盖变异行的测试（Python/pytest；零覆盖直接判 survived）")
    p.add_argument("--flaky", action="store_true", help="强制运行 flaky 检测")
    p.add_argument("--no-quality", action="store_true", help="跳过质量分析（弱断言/重复/flaky）")
    p.add_argument("--output-dir", default=None, help="报告输出目录（覆盖配置）")
    p.add_argument("--formats", default=None, help="报告格式，逗号分隔: html,json,junit_xml")
    p.add_argument("--allow-commands", action="store_true", help="允许执行配置中的命令（安全边界）")
    p.add_argument("--equivalents", default=None, help="等价变异标记文件（默认 .metatest/equivalents.yaml）")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("selftest", parents=[qv], help="元测试自检：运行已知答案基准项目，验证平台判断正确性")
    p.add_argument("--list", action="store_true", help="列出基准项目")
    p.add_argument("--case", action="append", default=[], help="只运行指定 case（可多次）")
    p.add_argument("--baseline-dir", default=None, help="基准项目目录（默认内置库）")
    p.add_argument("--json", default=None, help="自检结果 JSON 输出路径")
    p.set_defaults(func=cmd_selftest)

    p = sub.add_parser("flaky", parents=[qv], help="flaky 检测：重复运行测试统计不稳定率")
    common(p)
    p.add_argument("--runs", type=int, default=None, help="重复运行次数（默认配置值 3）")
    p.add_argument("--isolate", action="store_true",
                   help="对 flaky 测试单独复跑分类（isolated_flaky / order_dependent）")
    p.set_defaults(func=cmd_flaky)

    p = sub.add_parser("quality", parents=[qv], help="测试质量分析：弱断言 / 重复测试 / flaky")
    common(p)
    p.add_argument("--flaky", action="store_true", help="包含 flaky 检测")
    p.add_argument("--json", default=None, help="输出 JSON 路径")
    p.add_argument("--strict", action="store_true", help="发现问题时退出码 1")
    p.set_defaults(func=cmd_quality)

    p = sub.add_parser("report", help="从 results.json 重新渲染报告")
    p.add_argument("--results", required=True, help="results.json 路径")
    p.add_argument("--format", default="html", choices=["html", "junit_xml"], help="输出格式")
    p.add_argument("--out", required=True, help="输出文件路径")
    p.add_argument("--project-root", default=None, help="项目根（用于代码上下文）")
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("plugins", help="查看/生成插件")
    p.add_argument("plugins_cmd", nargs="?", default="list", choices=["list", "template"])
    p.add_argument("--dest", default=None, help="模板输出路径")
    p.set_defaults(func=cmd_plugins)

    p = sub.add_parser("ci", help="生成官方 CI 模板")
    p.add_argument("ci", choices=["github", "gitlab"], help="CI 平台")
    p.add_argument("--out", default=None, help="写入文件（默认打印）")
    p.set_defaults(func=cmd_ci)

    p = sub.add_parser("init", parents=[qv], help="生成 metatest.yaml（含布局推断与信任登记）")
    p.add_argument("dir", nargs="?", default=None, help="目标目录（默认当前目录）")
    p.add_argument("--language", default=None, choices=["python", "c", "command", None],
                   help="项目语言（默认自动探测）")
    p.add_argument("--force", action="store_true", help="覆盖已有配置")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("allow", help="显式信任一个配置（写入用户级存储，绑定内容指纹）")
    p.add_argument("--config", default=None, help="metatest.yaml 路径")
    p.add_argument("--project-root", default=None, help="项目根目录")
    p.set_defaults(func=cmd_allow)

    p = sub.add_parser("deny", help="撤销一个配置的信任")
    p.add_argument("--config", default=None, help="metatest.yaml 路径")
    p.add_argument("--project-root", default=None, help="项目根目录")
    p.set_defaults(func=cmd_deny)

    p = sub.add_parser("python", parents=[qv], help="查看/绑定运行测试用的 python 解释器")
    p.add_argument("--config", default=None, help="metatest.yaml 路径（用于定位项目根）")
    p.add_argument("--project-root", default=None, help="项目根目录")
    p.add_argument("--set", default=None, help="绑定解释器路径")
    p.add_argument("--clear", action="store_true", help="恢复自动探测")
    p.set_defaults(func=cmd_python)

    p = sub.add_parser("ui", parents=[qv], help="启动本地 Web 控制台（浏览器界面）")
    p.add_argument("--host", default="127.0.0.1", help="监听地址（默认仅本机）")
    p.add_argument("--port", type=int, default=0, help="端口（默认自动选择）")
    p.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    p.add_argument("--project", default=None, help="启动后直接打开某个项目目录")
    p.set_defaults(func=cmd_ui)

    return parser


def main(argv=None, sink=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # 无参数时默认 run（本地最常用）
    if not argv:
        argv = ["--help"]
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if getattr(args, "verbose", False) else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )
    out = Output(quiet=getattr(args, "quiet", False), sink=sink)
    # run 的 --quiet 透传
    if getattr(args, "cmd", None) == "run":
        out.quiet = args.quiet

    try:
        rc = args.func(args, out)
        return rc
    except ConfigError as e:
        out.important(f"[config] {e}")
        return EXIT_PLATFORM
    except MetaTestError as e:
        out.important(f"[error] {e}")
        return EXIT_PLATFORM
    except KeyboardInterrupt:
        out.important("\n[interrupt] 用户中断")
        return EXIT_PLATFORM


if __name__ == "__main__":
    sys.exit(main())
