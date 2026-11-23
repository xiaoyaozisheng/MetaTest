"""元测试自检（PRD FR-08）：用已知答案的基准项目验证平台自身判断的正确性。

基准项目类型（已知答案）：
  必失败 / 必通过 / 跳过 / 超时 / 弱断言 / flaky / 变异必杀死 / 变异必存活。

自检失败则平台自身不可信，CI 应失败（退出码 3）。
"""

from __future__ import annotations

import shutil
import tempfile
import time
from pathlib import Path
from typing import Optional

import yaml

from metatest.adapters import create_adapter
from metatest.config import load_config
from metatest.core.engine import MutationEngine
from metatest.core.quality import detect_flaky, find_weak_assertions
from metatest.errors import AdapterError, ConfigError
from metatest.models import SelfTestResult

DEFAULT_BASELINE_DIR = Path(__file__).resolve().parent.parent / "metatests"


class Case:
    def __init__(self, path: Path, spec: dict):
        self.dir = path.parent
        self.path = path
        self.spec = spec
        self.case_id = spec.get("case_id", path.parent.name)
        self.description = spec.get("description", "")
        self.kind = spec.get("kind", "test_run")

    @property
    def config_path(self) -> Path:
        cfg = self.spec.get("config", "metatest.yaml")
        return self.dir / cfg


def discover_cases(baseline_dir=None) -> list:
    base = Path(baseline_dir) if baseline_dir else DEFAULT_BASELINE_DIR
    cases = []
    if not base.exists():
        return cases
    for child in sorted(base.iterdir()):
        spec_file = child / "selftest.yaml"
        if child.is_dir() and spec_file.exists():
            try:
                spec = yaml.safe_load(spec_file.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError as e:
                cases.append(_broken_case(child, spec_file, str(e)))
                continue
            cases.append(Case(spec_file, spec))
    return cases


def _broken_case(parent: Path, spec_file: Path, error: str) -> Case:
    c = Case(spec_file, {"case_id": parent.name, "kind": "broken"})
    c.description = f"selftest.yaml 解析失败: {error}"
    return c


def run_selftest(cases: list, progress=None, case_filter=None, quiet=False) -> list:
    """执行自检：每个基准项目复制到独立临时目录运行，避免互相污染。"""
    progress = progress or (lambda msg: None)
    results = []
    for case in cases:
        if case_filter and case.case_id not in case_filter:
            continue
        started = time.monotonic()
        result = _run_case(case, progress)
        result.duration_sec = time.monotonic() - started
        results.append(result)
        icon = "PASS" if result.passed else ("SKIP" if result.skipped else "FAIL")
        progress(f"[selftest] {icon:4s} {result.case_id}: expected={result.expected} actual={result.actual}"
                 + (f" ({result.message})" if result.message else ""))
    return results


def _run_case(case: Case, progress) -> SelfTestResult:
    if case.kind == "broken":
        return SelfTestResult(case.case_id, case.description, case.kind, "可解析", "解析失败",
                              passed=False, message=case.description)
    tmp = Path(tempfile.mkdtemp(prefix="mt_case_"))
    try:
        # 复制基准项目（排除运行残留）
        shutil.copytree(
            case.dir, tmp, dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "_metatest_junit.xml",
                                          ".flaky_state", "build"),
        )
        handler = {
            "test_run": _case_test_run,
            "mutation": _case_mutation,
            "flaky": _case_flaky,
            "weak_assert": _case_weak_assert,
        }.get(case.kind)
        if handler is None:
            return SelfTestResult(case.case_id, case.description, case.kind, "已知 kind", f"未知 kind {case.kind!r}",
                                  passed=False, message=f"selftest.yaml 的 kind 无效: {case.kind}")
        return handler(case, tmp, progress)
    except AdapterError as e:
        return SelfTestResult(case.case_id, case.description, case.kind, "-", "-",
                              passed=True, skipped=True, message=f"环境缺失，跳过: {e}")
    except ConfigError as e:
        return SelfTestResult(case.case_id, case.description, case.kind, "配置有效", f"配置错误: {e}",
                              passed=False, message=str(e))
    except Exception as e:  # 平台崩溃 = 自检失败
        return SelfTestResult(case.case_id, case.description, case.kind, "平台正常", f"平台异常: {type(e).__name__}: {e}",
                              passed=False)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# kind=test_run：验证测试结果的正确分类（必失败/必通过/跳过/超时）
# ---------------------------------------------------------------------------


def _case_test_run(case: Case, tmp: Path, progress) -> SelfTestResult:
    cfg = load_config(case.config_path, project_root=tmp)
    adapter = create_adapter(cfg, tmp)
    adapter.prepare()
    timeout = float(case.spec.get("timeout_sec", cfg.timeout_sec))
    run = adapter.run_tests(tmp, timeout)
    expected = str(case.spec.get("expect", {}).get("outcome", ""))
    actual = run.outcome.value
    passed = actual == expected
    message = (f"tests={run.tests} failures={run.failures} errors={run.errors} "
               f"skipped={run.skipped} exit={run.exit_code}")
    # 跳过检测附加断言：必须解析出 skipped 用例数
    if expected == "pass_with_skips" and passed and run.skipped <= 0:
        passed = False
        message += "（应解析出 skipped>0）"
    if expected == "all_skipped" and passed and run.tests <= 0:
        passed = False
        message += "（应解析出 tests>0）"
    return SelfTestResult(case.case_id, case.description, case.kind,
                          f"outcome={expected}", f"outcome={actual}", passed, message=message)


# ---------------------------------------------------------------------------
# kind=mutation：验证变异判定（变异必杀死 / 必存活）
# ---------------------------------------------------------------------------


def _case_mutation(case: Case, tmp: Path, progress) -> SelfTestResult:
    cfg = load_config(case.config_path, project_root=tmp)
    adapter = create_adapter(cfg, tmp)
    adapter.prepare()
    expect = case.spec.get("expect", {})
    operators = case.spec.get("operators") or cfg.effective_operators()
    specs = adapter.generate_mutants(operators)
    mutants = [s.to_mutant() for s in _select_mutants(specs, expect.get("mutants", []))]
    if not mutants:
        return SelfTestResult(case.case_id, case.description, case.kind,
                              "生成目标变异体", "未生成任何匹配变异体", passed=False,
                              message=f"算子={operators}，总变异体={len(specs)}")
    engine = MutationEngine(cfg, tmp, adapter, progress=None)
    analysis = engine.run(mutants, no_cache=True)
    actual_parts, passed = [], True
    for sel in expect.get("mutants", []):
        matched = _match_mutant(mutants, sel)
        if matched is None:
            passed = False
            actual_parts.append(f"未找到 {sel.get('path')}:{sel.get('operator')}")
            continue
        want = sel.get("status")
        got = matched.status.value
        ok = got == want
        passed = passed and ok
        if "suspect" in sel and matched.suspect_equivalent != bool(sel["suspect"]):
            ok = False
            actual_parts.append(f"suspect={matched.suspect_equivalent}(期望{sel['suspect']})")
        actual_parts.append(f"{matched.location}[{matched.operator}]={got}(期望{want})")
    max_errors = expect.get("max_errors")
    if max_errors is not None and analysis.error > int(max_errors):
        passed = False
        actual_parts.append(f"errors={analysis.error}(期望≤{max_errors})")
    return SelfTestResult(case.case_id, case.description, case.kind,
                          "; ".join(f"{s.get('path')}:{s.get('operator')}→{s.get('status')}"
                                    for s in expect.get("mutants", [])),
                          "; ".join(actual_parts), passed,
                          message=f"score={analysis.score_percent()} errors={analysis.error}")


def _select_mutants(specs, selectors):
    """仅保留期望中点名的变异体，缩短自检时间。"""
    if not selectors:
        return specs
    selected = []
    for sel in selectors:
        for s in specs:
            if s.path.replace("\\", "/") == sel.get("path", "").replace("\\", "/") \
                    and s.operator == sel.get("operator"):
                if sel.get("original") and s.original != sel["original"]:
                    continue
                if sel.get("lineno") and s.lineno != sel["lineno"]:
                    continue
                selected.append(s)
    return selected


def _match_mutant(mutants, sel):
    for m in mutants:
        if m.path.replace("\\", "/") == sel.get("path", "").replace("\\", "/") \
                and m.operator == sel.get("operator"):
            if sel.get("original") and m.original != sel["original"]:
                continue
            if sel.get("lineno") and m.lineno != sel["lineno"]:
                continue
            return m
    return None


# ---------------------------------------------------------------------------
# kind=flaky / kind=weak_assert
# ---------------------------------------------------------------------------


def _case_flaky(case: Case, tmp: Path, progress) -> SelfTestResult:
    cfg = load_config(case.config_path, project_root=tmp)
    adapter = create_adapter(cfg, tmp)
    adapter.prepare()
    # flaky 基准约定：状态文件指向沙箱外的绝对路径，保证多次运行间状态累积
    state_file = tmp / ".flaky_state"
    if state_file.exists():
        state_file.unlink()
    cfg.env["FLAKY_STATE_FILE"] = str(state_file)
    runs = int(case.spec.get("runs", cfg.flaky.runs))
    flaky = detect_flaky(cfg, tmp, adapter, runs=runs)
    expect_flaky = bool(case.spec.get("expect", {}).get("flaky", True))
    actual = bool(flaky)
    passed = actual == expect_flaky
    names = ", ".join(f.test_id for f in flaky[:3])
    return SelfTestResult(case.case_id, case.description, case.kind,
                          f"flaky={expect_flaky}", f"flaky={actual}", passed,
                          message=f"检测到: {names}" if flaky else "未检测到 flaky")


def _case_weak_assert(case: Case, tmp: Path, progress) -> SelfTestResult:
    cfg = load_config(case.config_path, project_root=tmp)
    weak = find_weak_assertions(tmp, cfg.test_roots)
    flagged = {w.test for w in weak}
    expected_tests = set(case.spec.get("expect", {}).get("tests", []))
    missing = expected_tests - flagged
    passed = not missing
    return SelfTestResult(case.case_id, case.description, case.kind,
                          f"标记 {sorted(expected_tests)}", f"标记 {sorted(flagged)}", passed,
                          message=f"缺漏: {sorted(missing)}" if missing else "")
