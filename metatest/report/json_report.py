"""JSON 报告：机器可读的完整结果。"""

from __future__ import annotations

import json
import time
from pathlib import Path

from metatest import __version__
from metatest.models import AnalysisResult, QualityReport


def analysis_to_dict(analysis: AnalysisResult, quality: QualityReport | None = None,
                     selftest=None, config=None) -> dict:
    doc = {
        "schema": "metatest/results@1",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "metatest_version": __version__,
        "project": {
            "name": analysis.project_name,
            "language": config.language if config else None,
            "test_cmd": config.test_cmd if config else None,
        },
        "baseline": _run_to_dict(analysis.baseline),
        "summary": {
            "total": len(analysis.mutants),
            "killed": analysis.killed,
            "survived": analysis.survived,
            "timeout": analysis.timeout,
            "equivalent": analysis.equivalent,
            "error": analysis.error,
            "mutation_score": analysis.score,
            "mutation_score_percent": analysis.score_percent(),
            "duration_sec": round(analysis.duration_sec, 2),
        },
        "incremental": analysis.incremental,
        "test_selection": analysis.test_selection,
        "strategy": analysis.strategy,
        "operator_filter": analysis.operator_filter,
        "mutants": [_mutant_to_dict(m) for m in analysis.mutants],
        "engine_scores": analysis.engine_scores(),
        "file_scores": {
            path: {
                "killed": info["killed"],
                "survived": info["survived"],
                "scored": info["scored"],
                "score": round(info["score"], 4) if info["score"] is not None else None,
            }
            for path, info in analysis.file_scores().items()
        },
    }
    if quality is not None:
        doc["quality"] = quality.as_dict()
    if selftest is not None:
        doc["selftest"] = selftest
    return doc


def _run_to_dict(run) -> dict | None:
    if run is None:
        return None
    return {
        "exit_code": run.exit_code,
        "duration_sec": round(run.duration_sec, 2),
        "outcome": run.outcome.value,
        "tests": run.tests,
        "failures": run.failures,
        "errors": run.errors,
        "skipped": run.skipped,
        "failing_tests": run.failing_tests,
    }


def _mutant_to_dict(m) -> dict:
    return {
        "id": m.id,
        "path": m.path,
        "line": m.lineno,
        "operator": m.operator,
        "description": m.description,
        "original": m.original,
        "mutated": m.mutated,
        "status": m.status.value,
        "duration_sec": round(m.duration_sec, 3),
        "message": m.message,
        "failed_tests": m.failed_tests,
        "equivalent": m.equivalent,
        "suspect_equivalent": m.suspect_equivalent,
        "cached": m.cached,
        "covered_by": m.covered_by,
        "engine": m.engine,
    }


def write_json_report(analysis: AnalysisResult, path, quality=None, selftest=None, config=None,
                      gate=None) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = analysis_to_dict(analysis, quality=quality, selftest=selftest, config=config)
    if gate:
        doc["gate"] = gate
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def analysis_from_dict(doc: dict) -> AnalysisResult:
    """从 results.json 重建 AnalysisResult（metatest report 命令用）。"""
    from metatest.models import Mutant, MutantStatus, TestRunResult, RunOutcome

    analysis = AnalysisResult(project_name=doc.get("project", {}).get("name", "unnamed"))
    summary = doc.get("summary", {})
    analysis.duration_sec = summary.get("duration_sec", 0.0)
    analysis.operator_filter = doc.get("operator_filter")
    analysis.incremental = doc.get("incremental")
    b = doc.get("baseline")
    if b:
        run = TestRunResult(
            exit_code=b.get("exit_code"),
            duration_sec=b.get("duration_sec", 0.0),
            tests=b.get("tests", 0),
            failures=b.get("failures", 0),
            errors=b.get("errors", 0),
            skipped=b.get("skipped", 0),
            failing_tests=b.get("failing_tests", []),
        )
        try:
            run.outcome = RunOutcome(b.get("outcome", "error"))
        except ValueError:
            run.outcome = RunOutcome.ERROR
        analysis.baseline = run
    for m in doc.get("mutants", []):
        try:
            status = MutantStatus(m.get("status", "not_run"))
        except ValueError:
            status = MutantStatus.NOT_RUN
        mutant = Mutant(
            path=m.get("path", ""),
            start_offset=0,
            end_offset=0,
            lineno=m.get("line", 0),
            operator=m.get("operator", ""),
            original=m.get("original", ""),
            mutated=m.get("mutated", ""),
            description=m.get("description", ""),
            status=status,
            duration_sec=m.get("duration_sec", 0.0),
            message=m.get("message", ""),
            failed_tests=m.get("failed_tests", []),
            equivalent=m.get("equivalent", False),
            suspect_equivalent=m.get("suspect_equivalent", False),
            cached=m.get("cached", False),
        )
        mutant.id = m.get("id", mutant.stable_id())
        analysis.mutants.append(mutant)
    return analysis
