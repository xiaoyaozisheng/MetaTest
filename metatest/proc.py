"""子进程执行器：超时、进程树终止、输出截断（PRD FR-05）。"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

OUTPUT_TAIL_BYTES = 8 * 1024


@dataclass
class ProcResult:
    exit_code: Optional[int]
    duration_sec: float
    timed_out: bool = False
    output: str = ""
    killed_by_us: bool = False

    @property
    def output_tail(self) -> str:
        return self.output[-OUTPUT_TAIL_BYTES:] if self.output else ""


def kill_process_tree(pid: int) -> None:
    """跨平台终止进程树。"""
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            try:
                os.kill(pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass


def run_command(
    cmd: str,
    cwd,
    timeout: float,
    env_extra: Optional[dict] = None,
    shell: bool = True,
    capture: bool = True,
) -> ProcResult:
    """执行命令并在超时时终止整个进程树。

    Windows 上通过 cmd.exe 执行（shell=True）；POSIX 上使用新会话以便
    对整个进程组发送 SIGKILL。
    """
    start = time.monotonic()
    env = os.environ.copy()
    if env_extra:
        env.update({k: str(v) for k, v in env_extra.items()})

    popen_kwargs = {}
    if sys.platform != "win32":
        popen_kwargs["start_new_session"] = True

    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        shell=shell,
        stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
        stderr=subprocess.STDOUT if capture else subprocess.DEVNULL,
        env=env,
        **popen_kwargs,
    )

    timed_out = False
    output_holder = {"chunks": [], "size": 0}
    lock = threading.Lock()

    def _reader(stream):
        try:
            for raw in iter(stream.readline, b""):
                with lock:
                    output_holder["size"] += len(raw)
                    if output_holder["size"] <= OUTPUT_TAIL_BYTES * 4:
                        output_holder["chunks"].append(raw)
        except (ValueError, OSError):
            pass

    threads = []
    if capture:
        t = threading.Thread(target=_reader, args=(proc.stdout,), daemon=True)
        t.start()
        threads.append(t)

    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        kill_process_tree(proc.pid)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()

    for t in threads:
        t.join(timeout=5)

    duration = time.monotonic() - start
    with lock:
        raw_output = b"".join(output_holder["chunks"])
    # 只保留尾部，避免巨型日志占用内存
    raw_output = raw_output[-OUTPUT_TAIL_BYTES * 2:]
    output = _decode(raw_output)

    exit_code = proc.returncode if proc.returncode is not None else None
    if timed_out and exit_code is None:
        exit_code = -1
    return ProcResult(
        exit_code=exit_code,
        duration_sec=duration,
        timed_out=timed_out,
        output=output,
        killed_by_us=timed_out,
    )


def _decode(raw: bytes) -> str:
    for enc in ("utf-8", "utf-8-sig", "gbk", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def check_executable_available(cmd_probe: str, cwd=None) -> bool:
    """探测某命令是否可执行（用于适配器 prepare 检查）。"""
    try:
        result = run_command(cmd_probe, cwd=cwd or Path.cwd(), timeout=30, capture=True)
        return result.exit_code == 0
    except Exception:
        return False
