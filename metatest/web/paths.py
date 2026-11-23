"""资源路径解析：源码运行与 PyInstaller 打包运行（--onefile/--onedir）都可用。"""

from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def bundle_root() -> Path:
    """打包后被解包到的临时目录；源码运行时是包目录。"""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return Path(__file__).resolve().parent.parent.parent


def static_dir() -> Path:
    """前端静态资源目录。"""
    candidates = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "metatest" / "web" / "static")
        candidates.append(Path(meipass) / "static")
    candidates.append(Path(__file__).resolve().parent / "static")
    for c in candidates:
        if (c / "index.html").exists():
            return c
    return candidates[-1]
