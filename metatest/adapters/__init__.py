"""适配器注册表（PRD FR-02）：内置 + 插件扩展。"""

from __future__ import annotations

from pathlib import Path

from metatest.adapters.base import BaseAdapter
from metatest.adapters.c_adapter import CAdapter
from metatest.adapters.command_adapter import CommandAdapter
from metatest.adapters.python_adapter import PythonAdapter
from metatest.errors import AdapterError

ADAPTER_REGISTRY: dict = {
    "python": PythonAdapter,
    "c": CAdapter,
    "command": CommandAdapter,
}


def register_adapter(name: str, cls) -> None:
    """注册第三方适配器（供插件调用，PRD FR-10）。"""
    if not (isinstance(cls, type) and issubclass(cls, BaseAdapter)):
        raise AdapterError(f"适配器 {name!r} 注册失败：必须是 BaseAdapter 子类")
    ADAPTER_REGISTRY[name] = cls


def get_adapter_class(name: str):
    cls = ADAPTER_REGISTRY.get(name)
    if cls is None:
        known = ", ".join(sorted(ADAPTER_REGISTRY))
        raise AdapterError(f"未知适配器/语言: {name!r}（可用: {known}）")
    return cls


def create_adapter(config, project_root) -> BaseAdapter:
    cls = get_adapter_class(config.language)
    return cls(Path(project_root), config)


def detect_language(project_root) -> str:
    """自动探测项目语言（metatest init 用）。"""
    root = Path(project_root)
    best, best_score = "command", 0
    for name, cls in ADAPTER_REGISTRY.items():
        try:
            score = cls.detect(root)
        except Exception:
            score = 0
        if score > best_score:
            best, best_score = name, score
    return best
