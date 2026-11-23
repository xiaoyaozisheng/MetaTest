"""报告模块：HTML / JSON / JUnit XML（PRD FR-09）。"""

from __future__ import annotations

from pathlib import Path

from metatest.models import AnalysisResult, QualityReport
from metatest.report.html_report import write_html_report
from metatest.report.json_report import write_json_report
from metatest.report.junit_report import write_junit_report

FORMATS = ("html", "json", "junit_xml")


def write_reports(analysis: AnalysisResult, output_dir, config=None, quality: QualityReport | None = None,
                  selftest=None, project_root=None, gate=None, formats=None) -> dict:
    """按配置写出报告，返回 {format: 路径}。"""
    out = Path(output_dir)
    formats = formats or (config.report.formats if config else FORMATS)
    paths = {}
    if "json" in formats:
        paths["json"] = write_json_report(analysis, out / "results.json", quality=quality,
                                          selftest=selftest, config=config, gate=gate)
    if "html" in formats:
        paths["html"] = write_html_report(analysis, out / "report.html", quality=quality,
                                          selftest=selftest, config=config,
                                          project_root=project_root, gate=gate)
    if "junit_xml" in formats:
        paths["junit_xml"] = write_junit_report(analysis, out / "mutation_junit.xml")
    return paths
