"""变异结果缓存（PRD FR-05：未变更代码的变异结果可复用）。"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from pathlib import Path

from metatest.models import Mutant, MutantStatus

_CACHE_VERSION = 1
_CACHEABLE = {MutantStatus.KILLED, MutantStatus.SURVIVED, MutantStatus.TIMEOUT}


class ResultCache:
    """JSON 文件缓存，键为变异体与代码内容的复合哈希。"""

    def __init__(self, path, enabled: bool = True):
        self.path = Path(path)
        self.enabled = enabled
        self._data = {}
        self._dirty = False
        if enabled and self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
                if self._data.get("version") != _CACHE_VERSION:
                    self._data = {}
            except (OSError, ValueError):
                self._data = {}

    @staticmethod
    def key(cfg, mutant: Mutant, patched_hash: str) -> str:
        payload = json.dumps(
            [
                _CACHE_VERSION,
                cfg.name,
                cfg.language,
                cfg.test_cmd,
                cfg.test_result_format,
                cfg.timeout_sec,
                mutant.path,
                mutant.operator,
                mutant.start_offset,
                mutant.end_offset,
                mutant.original,
                mutant.mutated,
                patched_hash,
            ],
            ensure_ascii=False,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def get(self, key: str):
        entry = self._data.get("entries", {}).get(key)
        if not entry:
            return None
        try:
            status = MutantStatus(entry["status"])
        except (KeyError, ValueError):
            return None
        if status not in _CACHEABLE:
            return None
        return entry

    def put(self, key: str, mutant: Mutant) -> None:
        if not self.enabled or mutant.status not in _CACHEABLE:
            return
        self._data.setdefault("entries", {})[key] = {
            "status": mutant.status.value,
            "duration_sec": round(mutant.duration_sec, 3),
            "message": mutant.message,
            "failed_tests": mutant.failed_tests,
            "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        self._dirty = True

    def save(self) -> None:
        if not (self.enabled and self._dirty):
            return
        self._data["version"] = _CACHE_VERSION
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # 原子写：并发 run（本地多终端 / CI 并行 job）共用缓存文件时，
        # 直接 write_text 会交错写坏 JSON。先写临时文件再 os.replace。
        # 临时文件名带 pid + 线程号：同一进程内并发保存/多线程写同一路径在 Windows 上会
        # 因文件被占用抛 PermissionError（缓存只是优化，失败应降级而不是让任务崩溃）
        tmp = self.path.with_suffix(
            self.path.suffix + f".tmp{os.getpid()}-{threading.get_ident()}"
        )
        try:
            tmp.write_text(json.dumps(self._data, ensure_ascii=False, indent=1), encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError:
            tmp.unlink(missing_ok=True)  # 极端争用下放弃本轮持久化（内存结果不受影响）

    def size(self) -> int:
        return len(self._data.get("entries", {}))
