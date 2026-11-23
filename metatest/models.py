"""核心数据模型（对应 PRD 第 8 节概念级数据模型）。

ProjectConfig 见 metatest/config.py。
"""

from __future__ import annotations

import enum
import time
from dataclasses import dataclass, field
from typing import Optional


class MutantStatus(str, enum.Enum):
    """变异体结果判定（PRD FR-06）。"""

    NOT_RUN = "not_run"        # 尚未执行（被增量/等价过滤前初始状态）
    KILLED = "killed"          # 测试失败，测试发现了变异
    SURVIVED = "survived"      # 测试通过，测试漏测
    TIMEOUT = "timeout"        # 执行超时，单独统计
    EQUIVALENT = "equivalent"  # 人工标记或启发式判定为等价变异
    ERROR = "error"            # 构建/执行错误，不计入得分但需报告


# 计入变异得分分母的状态（等价变异体排除，error 不计入得分）
SCORED_STATUSES = (MutantStatus.KILLED, MutantStatus.SURVIVED, MutantStatus.TIMEOUT)


class RunOutcome(str, enum.Enum):
    """一次测试命令运行的整体结果分类。"""

    PASS = "pass"                        # 全部通过且无跳过
    PASS_WITH_SKIPS = "pass_with_skips"  # 无失败但有跳过（不可当作完全可信的通过）
    FAIL = "fail"                        # 存在失败/错误
    TIMEOUT = "timeout"                  # 命令超时被终止
    ERROR = "error"                      # 命令本身无法执行 / 结果文件缺失
    ALL_SKIPPED = "all_skipped"          # 所有测试均被跳过（不可当作通过）


def classify_run(
    exit_code: Optional[int],
    tests: int,
    failures: int,
    errors: int,
    skipped: int,
    timed_out: bool = False,
    has_junit: bool = True,
) -> RunOutcome:
    """根据测试命令结果判定整体结果。

    元测试关键点：跳过不等于通过。skipped 占比过高或全部跳过时，
    结果不能被当成可信的通过。
    """
    if timed_out:
        return RunOutcome.TIMEOUT
    if failures > 0 or errors > 0:
        return RunOutcome.FAIL
    if tests > 0 and skipped == tests:
        return RunOutcome.ALL_SKIPPED
    if failures == 0 and errors == 0 and skipped > 0:
        return RunOutcome.PASS_WITH_SKIPS
    if exit_code is None:
        return RunOutcome.ERROR
    if exit_code != 0:
        if has_junit and tests > 0:
            # 有结果文件但没有记录失败（如工具异常退出）
            return RunOutcome.FAIL
        if exit_code in (127, 126, 9009):
            # 命令不存在（127/126 POSIX、9009 Windows cmd）
            return RunOutcome.ERROR
        return RunOutcome.FAIL
    return RunOutcome.PASS


@dataclass
class TestRunResult:
    """一次测试命令运行（PRD TestRun 实体）。"""

    exit_code: Optional[int] = None
    duration_sec: float = 0.0
    timed_out: bool = False
    junit_path: Optional[str] = None
    tests: int = 0
    failures: int = 0
    errors: int = 0
    skipped: int = 0
    failing_tests: list = field(default_factory=list)
    output_tail: str = ""
    outcome: RunOutcome = RunOutcome.ERROR

    def classify(self) -> RunOutcome:
        self.outcome = classify_run(
            self.exit_code,
            self.tests,
            self.failures,
            self.errors,
            self.skipped,
            timed_out=self.timed_out,
            has_junit=self.junit_path is not None,
        )
        return self.outcome

    def is_clean_pass(self) -> bool:
        """可信的通过：无失败、无错误、无跳过。"""
        return self.outcome == RunOutcome.PASS


@dataclass
class Mutant:
    """变异体（PRD Mutant 实体）。

    位置采用字符偏移（源码文本内），lineno 为 1 起始行号用于展示。
    """

    path: str                    # 项目相对路径（posix 风格）
    start_offset: int            # 源文件字符偏移（闭区间起点）
    end_offset: int              # 源文件字符偏移（开区间终点）
    lineno: int                  # 1 起始行号（展示用）
    operator: str                # 变异算子名称
    original: str                # 原始片段
    mutated: str                 # 变异后片段
    description: str = ""        # 人可读描述
    id: str = ""                 # 稳定标识，用于缓存与等价标记
    status: MutantStatus = MutantStatus.NOT_RUN
    duration_sec: float = 0.0
    message: str = ""            # 判定补充信息（如失败测试名、错误摘要）
    failed_tests: list = field(default_factory=list)
    equivalent: bool = False              # 人工标记或启发式判定为等价
    suspect_equivalent: bool = False      # 启发式标记的可疑等价（不改变判定）
    cached: bool = False
    covered_by: int = 0                   # 覆盖该变异行的测试数（test_selection 模式）
    engine: str = ""                      # 生成引擎：ast / tree_sitter / fallback（可信度统计用）
    source_root: Optional[str] = None     # 所属源码根目录（增量/报告用）

    def stable_id(self) -> str:
        if not self.id:
            self.id = (
                f"{self.path}::{self.lineno}::{self.operator}"
                f"::{self.original}->{self.mutated}"
            )
        return self.id

    @property
    def location(self) -> str:
        return f"{self.path}:{self.lineno}"

    @property
    def change(self) -> str:
        return f"{self.original} -> {self.mutated}"


@dataclass
class AnalysisResult:
    """变异分析结果（PRD AnalysisResult 实体）。"""

    project_name: str
    baseline: Optional[TestRunResult] = None
    mutants: list = field(default_factory=list)
    duration_sec: float = 0.0
    started_at: float = field(default_factory=time.time)
    incremental: Optional[dict] = None       # 增量模式信息（模式、来源、过滤数量）
    test_selection: Optional[dict] = None    # 测试关联筛选信息（测试数、构建耗时）
    strategy: Optional[dict] = None          # 变异策略选择链（统一入口，详见 mutators/__init__.py）
    operator_filter: Optional[list] = None

    def count(self, status: MutantStatus) -> int:
        return sum(1 for m in self.mutants if m.status == status)

    @property
    def killed(self) -> int:
        return self.count(MutantStatus.KILLED)

    @property
    def survived(self) -> int:
        return self.count(MutantStatus.SURVIVED)

    @property
    def timeout(self) -> int:
        return self.count(MutantStatus.TIMEOUT)

    @property
    def equivalent(self) -> int:
        return self.count(MutantStatus.EQUIVALENT)

    @property
    def error(self) -> int:
        return self.count(MutantStatus.ERROR)

    @property
    def executed(self) -> int:
        return self.count(MutantStatus.KILLED) + self.count(MutantStatus.SURVIVED) + self.count(MutantStatus.TIMEOUT)

    @property
    def score(self) -> Optional[float]:
        """Mutation Score = killed / (killed + survived + timeout)。

        等价变异体从分母排除（PRD FR-06）。分母为 0 时返回 None（无法计算）。
        """
        denominator = self.count(MutantStatus.KILLED) + self.count(MutantStatus.SURVIVED) + self.count(MutantStatus.TIMEOUT)
        if denominator == 0:
            return None
        return self.count(MutantStatus.KILLED) / denominator

    def score_percent(self) -> Optional[float]:
        s = self.score
        return None if s is None else round(s * 100.0, 1)

    def mutants_by_file(self) -> dict:
        files = {}
        for m in self.mutants:
            files.setdefault(m.path, []).append(m)
        return files

    def file_scores(self) -> dict:
        """每个文件的 (killed, scored, score)。"""
        result = {}
        for path, ms in self.mutants_by_file().items():
            killed = sum(1 for m in ms if m.status == MutantStatus.KILLED)
            scored = sum(1 for m in ms if m.status in SCORED_STATUSES)
            score = (killed / scored) if scored else None
            result[path] = {"killed": killed, "scored": scored, "score": score,
                            "survived": sum(1 for m in ms if m.status == MutantStatus.SURVIVED)}
        return result

    def engine_scores(self) -> dict:
        """按生成引擎分组的得分（词法级回退的可信度审计用）。

        {engine: {total, killed, survived, timeout, error, equivalent, score}}
        """
        result = {}
        for m in self.mutants:
            engine = m.engine or "unknown"
            g = result.setdefault(engine, {"total": 0, "killed": 0, "survived": 0,
                                           "timeout": 0, "error": 0, "equivalent": 0})
            g["total"] += 1
            if m.status in SCORED_STATUSES:
                g[m.status.value] += 1
            elif m.status == MutantStatus.EQUIVALENT:
                g["equivalent"] += 1
            elif m.status == MutantStatus.ERROR:
                g["error"] += 1
        for g in result.values():
            scored = g["killed"] + g["survived"] + g["timeout"]
            g["score"] = round(g["killed"] / scored, 4) if scored else None
        return result


@dataclass
class SelfTestResult:
    """元测试自检结果（PRD SelfTestResult 实体）。"""

    case_id: str
    description: str
    kind: str
    expected: str
    actual: str
    passed: bool
    skipped: bool = False
    message: str = ""
    duration_sec: float = 0.0

    def as_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "description": self.description,
            "kind": self.kind,
            "expected": self.expected,
            "actual": self.actual,
            "pass": self.passed,
            "skipped": self.skipped,
            "message": self.message,
            "duration_sec": round(self.duration_sec, 3),
        }


@dataclass
class FlakyTest:
    """flaky 测试条目。"""

    test_id: str          # classname.name
    runs: int
    passed: int
    failed: int
    unstable_rate: float  # 不稳定率：与大多数结果不一致的运行占比
    is_flaky: bool
    mode: str = "suite_flaky"  # isolated_flaky（单独运行也 flaky）| order_dependent（套件内才 flaky，顺序/共享状态依赖）| isolated_failing（单独运行恒失败）

    def as_dict(self) -> dict:
        return {
            "test_id": self.test_id,
            "runs": self.runs,
            "passed": self.passed,
            "failed": self.failed,
            "unstable_rate": round(self.unstable_rate, 3),
            "flaky": self.is_flaky,
            "mode": self.mode,
        }


@dataclass
class WeakAssertion:
    """弱断言条目。"""

    file: str
    test: str
    lineno: int
    reason: str           # no_assertion / trivial_assert / constant_assert / low_assertions

    def as_dict(self) -> dict:
        return {"file": self.file, "test": self.test, "line": self.lineno, "reason": self.reason}


@dataclass
class QualityReport:
    """测试质量报告（PRD QualityReport 实体，FR-07）。"""

    flaky_tests: list = field(default_factory=list)
    weak_assertions: list = field(default_factory=list)
    duplicate_tests: list = field(default_factory=list)   # [(fileA, testA, fileB, testB)]
    high_coverage_low_mutation: list = field(default_factory=list)  # [{file, coverage, score}]
    suggestions: list = field(default_factory=list)
    axes: Optional[dict] = None   # 三轴质量评分（adequacy/redundancy/maintainability）

    def as_dict(self) -> dict:
        return {
            "flaky_tests": [f.as_dict() for f in self.flaky_tests],
            "weak_assertions": [w.as_dict() for w in self.weak_assertions],
            "duplicate_tests": [list(d) for d in self.duplicate_tests],
            "high_coverage_low_mutation": self.high_coverage_low_mutation,
            "suggestions": self.suggestions,
            "axes": self.axes,
        }

    def has_findings(self) -> bool:
        return bool(
            self.flaky_tests or self.weak_assertions or self.duplicate_tests or self.high_coverage_low_mutation
        )


def build_suggestions(analysis: Optional[AnalysisResult], quality: Optional[QualityReport]) -> list:
    """输出可操作建议（PRD FR-07）。"""
    tips = []
    if analysis is not None:
        survivors = [m for m in analysis.mutants if m.status == MutantStatus.SURVIVED]
        by_op = {}
        for m in survivors:
            by_op.setdefault(m.operator, []).append(m)
        for op, ms in sorted(by_op.items(), key=lambda kv: -len(kv[1])):
            loc = ms[0].location
            tips.append(
                f"算子 [{op}] 有 {len(ms)} 个漏测变异，示例 {loc}（{ms[0].change}）："
                f"为该分支补充边界/分支断言。"
            )
        if analysis.baseline is not None and analysis.baseline.skipped:
            tips.append(
                f"基线测试运行包含 {analysis.baseline.skipped} 个跳过用例：确认跳过是否符合预期，"
                "避免“跳过被误判为通过”。"
            )
    if quality is not None:
        if quality.flaky_tests:
            names = ", ".join(f.test_id for f in quality.flaky_tests[:5])
            tips.append(f"检测到 {len(quality.flaky_tests)} 个 flaky 测试（{names}…）：修复时间/顺序/随机依赖。")
        if quality.weak_assertions:
            tips.append(f"检测到 {len(quality.weak_assertions)} 个弱断言测试：为它们补充明确断言或移除。")
        if quality.duplicate_tests:
            tips.append(f"检测到 {len(quality.duplicate_tests)} 组重复测试：合并或参数化。")
        if quality.high_coverage_low_mutation:
            for item in quality.high_coverage_low_mutation[:5]:
                tips.append(
                    f"文件 {item['file']} 覆盖率高（{item['coverage']:.0%}）但变异得分低"
                    f"（{item['score']:.0%}）：测试在“执行”而非“验证”，补充有效断言。"
                )
    return tips
