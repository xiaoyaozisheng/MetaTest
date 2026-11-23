"""任务队列：在后台线程中执行 CLI 命令，日志与进度供前端订阅。

设计取舍：
  * 单工作线程 + FIFO 队列 —— 变异测试本身是重 CPU/IO 任务，串行执行避免多个
    项目同时抢占 CPU 导致超时判定失真；排队状态对用户可见。
  * 每个任务通过 ``job.append`` 接收 CLI 输出（cli.main 的 sink 参数），
    同时从 ``[done/total]`` 行解析进度。
"""

from __future__ import annotations

import queue
import re
import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field

MAX_LOG_LINES = 4000
_PROGRESS_RE = re.compile(r"^\[(\d+)/(\d+)\]\s")
_STATUS_RE = re.compile(r"^\[(\d+)/(\d+)\]\s+(\w+)\s")

TERMINAL = ("done", "failed", "cancelled")


@dataclass
class Job:
    id: str
    kind: str                    # run / selftest / quality
    title: str
    project: str | None
    argv: list
    meta: dict = field(default_factory=dict)
    status: str = "queued"       # queued / running / done / failed / cancelled
    exit_code: int | None = None
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None
    logs: list = field(default_factory=list)
    progress: dict = field(default_factory=dict)
    result: dict | None = None
    error: str | None = None
    _cond: threading.Condition = field(default_factory=threading.Condition, repr=False)

    # -- 日志 -----------------------------------------------------------

    def append(self, text: str) -> None:
        if text is None:
            return
        lines = str(text).replace("\r\n", "\n").replace("\r", "\n").split("\n")
        with self._cond:
            for line in lines:
                if not line.strip():
                    continue
                self._add_line(line)
            self._cond.notify_all()

    def _add_line(self, line: str) -> None:
        entry = {
            "i": len(self.logs),
            "t": round(time.time(), 3),
            "lvl": _level_of(line),
            "text": line.rstrip(),
        }
        self.logs.append(entry)
        if len(self.logs) > MAX_LOG_LINES:
            # 只保留尾部；索引继续递增，前端按 i 去重
            drop = len(self.logs) - MAX_LOG_LINES
            self.logs = self.logs[drop:]
        m = _PROGRESS_RE.match(line)
        if m:
            done, total = int(m.group(1)), int(m.group(2))
            by = dict(self.progress.get("by_status") or {})
            sm = _STATUS_RE.match(line)
            if sm:
                by[sm.group(3)] = by.get(sm.group(3), 0) + 1
            self.progress = {"done": done, "total": total, "by_status": by}

    # -- 状态 -----------------------------------------------------------

    def mark_state(self, status: str, exit_code: int | None = None, error: str | None = None) -> None:
        with self._cond:
            self.status = status
            if status == "running" and self.started_at is None:
                self.started_at = time.time()
            if status in TERMINAL:
                self.finished_at = time.time()
            if exit_code is not None:
                self.exit_code = exit_code
            if error:
                self.error = error
            self._cond.notify_all()

    def is_terminal(self) -> bool:
        return self.status in TERMINAL

    # -- 快照 -----------------------------------------------------------

    def summary(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "title": self.title,
            "project": self.project,
            "status": self.status,
            "exit_code": self.exit_code,
            "created_at": round(self.created_at, 3),
            "started_at": round(self.started_at, 3) if self.started_at else None,
            "finished_at": round(self.finished_at, 3) if self.finished_at else None,
            "progress": self.progress,
            "error": self.error,
            "log_count": len(self.logs),
            "has_result": self.result is not None,
        }

    def snapshot(self, since: int = 0, with_result: bool = True) -> dict:
        with self._cond:
            logs = [e for e in self.logs if e["i"] >= since]
            data = self.summary()
            data["logs"] = logs
            if with_result:
                data["result"] = self.result
            return data

    def wait_for_logs(self, since: int, timeout: float = 20.0) -> tuple:
        """返回 (日志条目, 状态的终态标记)。"""
        with self._cond:
            if not any(e["i"] >= since for e in self.logs) and not self.is_terminal():
                self._cond.wait(timeout)
            return [e for e in self.logs if e["i"] >= since], self.is_terminal()


def _level_of(line: str) -> str:
    low = line.lower()
    head = low[:14]
    if "[error]" in head or "[config]" in head or "✗" in line or "traceback" in low:
        return "error"
    if ("未达标" in line or "超时" in line or "timeout" in low or "失败" in line
            or "未通过" in line or "缺失" in line):
        return "warn"
    if line.strip().startswith("=" * 10):
        return "muted"
    return "info"


class JobManager:
    def __init__(self, runner=None, retain: int = 50):
        self._jobs: dict = {}
        self._order: list = []
        self._queue: queue.Queue = queue.Queue()
        self._lock = threading.Lock()
        self._retain = retain
        self._runner = runner or _default_runner
        self._worker = threading.Thread(target=self._loop, name="metatest-job-worker", daemon=True)
        self._worker.start()

    # -- API ------------------------------------------------------------

    def submit(self, kind: str, argv: list, title: str, project: str | None = None,
               meta: dict | None = None, collector=None) -> Job:
        job = Job(
            id=uuid.uuid4().hex[:10],
            kind=kind,
            title=title,
            project=project,
            argv=list(argv),
            meta=meta or {},
        )
        with self._lock:
            self._jobs[job.id] = job
            self._order.append(job.id)
            self._trim()
        self._queue.put((job, collector))
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self, limit: int = 20) -> list:
        with self._lock:
            ids = list(reversed(self._order))[:limit]
            return [self._jobs[i].summary() for i in ids if i in self._jobs]

    def running_count(self) -> int:
        with self._lock:
            return sum(1 for j in self._jobs.values() if j.status in ("queued", "running"))

    # -- 内部 ------------------------------------------------------------

    def _trim(self) -> None:
        while len(self._order) > self._retain:
            old = self._order.pop(0)
            job = self._jobs.get(old)
            if job is not None and not job.is_terminal():
                self._order.append(old)
                return
            self._jobs.pop(old, None)

    def _loop(self) -> None:
        while True:
            job, collector = self._queue.get()
            job.mark_state("running")
            try:
                rc = self._runner(job)
                job.mark_state("done", exit_code=rc)
                if collector is not None:
                    try:
                        job.result = collector(job)
                    except Exception as e:  # 结果收集失败不影响任务结束
                        job.result = {"error": f"结果收集失败: {e}"}
            except Exception as e:
                job.append(f"[error] 任务异常: {e}")
                job.append(traceback.format_exc(limit=3))
                job.mark_state("failed", exit_code=2, error=str(e))


def _default_runner(job: Job) -> int:
    from metatest.cli.main import main as cli_main

    return cli_main(job.argv, sink=job.append)
