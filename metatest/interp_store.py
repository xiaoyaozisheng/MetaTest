"""用户级解释器绑定：为某个项目指定用来跑测试的 python。

为什么放在用户级而不是仓库配置：解释器路径是本机事实（Windows 的 D:\\Python、
Linux 的 venv），随仓库提交既无意义也不安全。存储位置 ``~/.metatest/interpreters.json``，
键为项目根目录绝对路径，值为解释器可执行文件路径。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def store_path() -> Path:
    return Path.home() / ".metatest" / "interpreters.json"


def _norm(project_root) -> str:
    text = str(Path(project_root).expanduser().resolve())
    return text.lower() if sys.platform == "win32" else text


def load_all() -> dict:
    try:
        data = json.loads(store_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_all(data: dict) -> None:
    p = store_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_assigned(project_root) -> str | None:
    entry = load_all().get(_norm(project_root))
    if isinstance(entry, dict):
        exe = entry.get("executable")
    else:
        exe = entry
    return exe if exe and Path(exe).exists() else None


def assign(project_root, executable: str) -> None:
    exe = str(Path(executable).expanduser().resolve())
    if not Path(exe).exists():
        raise FileNotFoundError(f"解释器不存在: {exe}")
    data = load_all()
    data[_norm(project_root)] = {"executable": exe}
    save_all(data)


def clear(project_root) -> bool:
    data = load_all()
    if _norm(project_root) in data:
        data.pop(_norm(project_root), None)
        save_all(data)
        return True
    return False
