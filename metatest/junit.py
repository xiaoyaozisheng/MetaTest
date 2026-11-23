"""JUnit XML 解析（统一结果输入，PRD FR-02/FR-09：优先 JUnit XML 降低多语言接入成本）。

兼容两类形态：
* pytest / unittest(xmlrunner): <testsuite ...><testcase><failure|error|skipped>
* CTest --output-junit:          <testsuites><testsuite ...><testcase status="passed|failed">
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from metatest.models import TestRunResult


@dataclass
class JunitCase:
    classname: str
    name: str
    status: str  # passed | failed | error | skipped
    message: str = ""
    time: float = 0.0

    @property
    def test_id(self) -> str:
        if self.classname:
            return f"{self.classname}.{self.name}"
        return self.name


@dataclass
class JunitSummary:
    tests: int = 0
    failures: int = 0
    errors: int = 0
    skipped: int = 0
    cases: list = field(default_factory=list)


def parse_junit(path) -> JunitSummary:
    """解析 JUnit XML 文件。文件损坏时抛出 ValueError。

    计数优先级：根元素聚合属性 → testsuite 属性求和 → 逐用例统计兜底。
    """
    p = Path(path)
    if not p.exists() or p.stat().st_size == 0:
        raise ValueError(f"JUnit XML 不存在或为空: {p}")
    try:
        root = ET.parse(p).getroot()
    except ET.ParseError as e:
        raise ValueError(f"JUnit XML 解析失败: {p}: {e}")

    summary = JunitSummary()
    suites = []
    if root.tag == "testsuites":
        suites = list(root)
        summary.tests = _int(root.get("tests"), 0)
        summary.failures = _int(root.get("failures"), 0)
        summary.errors = _int(root.get("errors"), 0)
        summary.skipped = _int(root.get("skipped") or root.get("disabled") or 0, 0)
    elif root.tag == "testsuite":
        suites = [root]
    else:
        raise ValueError(f"不是 JUnit XML 根元素: <{root.tag}>")

    agg = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    for suite in suites:
        if suite.tag != "testsuite":
            continue
        agg["tests"] += _int(suite.get("tests"), 0)
        agg["failures"] += _int(suite.get("failures"), 0)
        agg["errors"] += _int(suite.get("errors"), 0)
        agg["skipped"] += _int(suite.get("skipped") or suite.get("disabled") or 0, 0)
        for case in suite.iter("testcase"):
            status = None
            message = ""
            if case.find("failure") is not None:
                status = "failed"
                message = (case.find("failure").get("message") or "").strip()
            elif case.find("error") is not None:
                status = "error"
                message = (case.find("error").get("message") or "").strip()
            elif case.find("skipped") is not None:
                status = "skipped"
                message = (case.find("skipped").get("message") or "").strip()
            else:
                attr_status = (case.get("status") or "").lower()
                if attr_status in ("passed", "failed", "error", "skipped"):
                    status = attr_status
                    if status == "failed":
                        message = (case.get("message") or "").strip()
                elif attr_status in ("notrun", "not_run"):
                    status = "skipped"
                else:
                    status = "passed"
            classname = case.get("classname") or ""
            name = case.get("name") or ""
            summary.cases.append(
                JunitCase(
                    classname=classname,
                    name=name,
                    status=status or "passed",
                    message=message,
                    time=_float(case.get("time"), 0.0),
                )
            )

    # 用例级统计兜底
    case_counts = {
        "tests": len(summary.cases),
        "failures": sum(1 for c in summary.cases if c.status == "failed"),
        "errors": sum(1 for c in summary.cases if c.status == "error"),
        "skipped": sum(1 for c in summary.cases if c.status == "skipped"),
    }
    def _pick(field):
        # 优先根/suite 聚合值；聚合缺失或为 0 而用例统计有值时回退
        return summary.__getattribute__(field) or agg[field] or case_counts[field]

    summary.tests = _pick("tests")
    summary.failures = _pick("failures")
    summary.errors = _pick("errors")
    summary.skipped = _pick("skipped")
    return summary


def _int(v, default):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def _float(v, default):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def apply_summary(run: TestRunResult, summary: JunitSummary) -> TestRunResult:
    """把 JUnit 汇总信息写入 TestRunResult。"""
    run.tests = summary.tests
    run.failures = summary.failures
    run.errors = summary.errors
    run.skipped = summary.skipped
    run.failing_tests = [
        c.test_id for c in summary.cases if c.status in ("failed", "error")
    ]
    return run


def extract_junit_path(test_cmd: str, default_name: str) -> Optional[str]:
    """从测试命令里推断 JUnit 输出路径（相对路径原样返回）。"""
    import re

    patterns = [
        r"--junit-xml[= ](?:\"([^\"]+)\"|'([^']+)'|(\S+))",
        r"--junitxml[= ](?:\"([^\"]+)\"|'([^']+)'|(\S+))",
        r"--output-junit[= ](?:\"([^\"]+)\"|'([^']+)'|(\S+))",
        r"-o\s+junit_xml[= ](?:\"([^\"]+)\"|'([^']+)'|(\S+))",
    ]
    for pat in patterns:
        m = re.search(pat, test_cmd)
        if m:
            for g in m.groups():
                if g:
                    return g
    return None
