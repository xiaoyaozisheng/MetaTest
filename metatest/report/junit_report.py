"""JUnit XML 报告：把变异体映射为 JUnit 测试用例，CI 原生可视化。

* killed     → 通过的 testcase（测试套件成功"杀死"变异）
* survived   → <failure>（漏测变异 = 质量问题）
* timeout    → <failure type="timeout">
* equivalent → <skipped>（等价变异，不计分）
* error      → <error>（构建/执行问题）
"""

from __future__ import annotations

import xml.sax.saxutils as sax
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, ElementTree

from metatest.models import AnalysisResult, MutantStatus


def build_junit_tree(analysis: AnalysisResult) -> Element:
    total = len(analysis.mutants)
    failures = analysis.survived + analysis.timeout
    errors = analysis.error
    skipped = analysis.equivalent
    suite = Element("testsuite", {
        "name": "metatest-mutation",
        "tests": str(total),
        "failures": str(failures),
        "errors": str(errors),
        "skipped": str(skipped),
        "time": f"{analysis.duration_sec:.2f}",
    })
    props = SubElement(suite, "properties")
    if analysis.score is not None:
        SubElement(props, "property", {"name": "mutation_score", "value": f"{analysis.score * 100:.1f}"})
    SubElement(props, "property", {"name": "project", "value": analysis.project_name})
    if analysis.baseline is not None:
        SubElement(props, "property", {"name": "baseline_outcome", "value": analysis.baseline.outcome.value})

    for m in analysis.mutants:
        name = f"{m.path}:{m.lineno} [{m.operator}] {m.original}->{m.mutated}"
        case = SubElement(suite, "testcase", {
            "classname": f"mutation.{Path(m.path).with_suffix('')}",
            "name": name,
            "time": f"{m.duration_sec:.3f}",
        })
        if m.status == MutantStatus.KILLED:
            continue  # 通过的用例无需子元素
        if m.status == MutantStatus.SURVIVED:
            msg = f"漏测变异（survived）: {m.location} {m.description} [{m.original} -> {m.mutated}]"
            failure = SubElement(case, "failure", {"message": sax.escape(msg)[:400], "type": "survived_mutant"})
            failure.text = m.message or "测试通过，未能发现该变异"
        elif m.status == MutantStatus.TIMEOUT:
            failure = SubElement(case, "failure", {"message": f"变异导致测试超时: {m.location}", "type": "timeout"})
            failure.text = m.message
        elif m.status == MutantStatus.EQUIVALENT:
            skipped_el = SubElement(case, "skipped", {"message": "equivalent mutant（等价变异，不计入得分）"})
            skipped_el.text = m.message
        elif m.status == MutantStatus.ERROR:
            error_el = SubElement(case, "error", {"message": (m.message or "变异构建/执行失败")[:400], "type": "error"})
            error_el.text = m.message
        else:
            skipped_el = SubElement(case, "skipped", {"message": "not run"})
            skipped_el.text = m.message
    return suite


def write_junit_report(analysis: AnalysisResult, path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    root = Element("testsuites")
    suite = build_junit_tree(analysis)
    root.append(suite)
    tree = ElementTree(root)
    tree.write(str(path), encoding="utf-8", xml_declaration=True)
    return path
