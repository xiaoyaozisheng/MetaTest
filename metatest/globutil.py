"""globstar 兼容的 fnmatch：** 跨目录段，其余语义与 fnmatch 一致。

fnmatch 的 * 本就跨 "/"，因此普通模式行为不变；仅当模式包含 ** 时
额外提供 globstar 正则匹配（src/**/*.go 匹配 src 下任意深度的 .go）。
"""

from __future__ import annotations

import fnmatch
import re
from functools import lru_cache


@lru_cache(maxsize=256)
def _globstar_regex(pattern: str):
    parts = []
    segments = pattern.split("/")
    for idx, seg in enumerate(segments):
        if seg == "**":
            parts.append("(?:[^/]+/)*")
            continue
        rx = ""
        for ch in seg:
            if ch == "*":
                rx += "[^/]*"
            elif ch == "?":
                rx += "[^/]"
            else:
                rx += re.escape(ch)
        parts.append(rx)
        if idx != len(segments) - 1:
            parts.append("/")
    return re.compile("".join(parts) + "$")


def match(name: str, pattern: str) -> bool:
    if fnmatch.fnmatch(name, pattern):
        return True
    if "**" in pattern:
        return bool(_globstar_regex(pattern).match(name))
    return False
