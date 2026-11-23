"""插件机制（PRD FR-10）：变异算子插件、语言适配器插件。

加载方式：
  * entry_points 组 "metatest.plugins"（安装包形式分发）
  * 配置 plugins.dirs / CLI --plugin-dir（本地目录：单个 .py 或含 __init__.py 的包）

插件契约：模块提供 register(ctx) 函数；ctx 提供注册 API（见 templates/）。
"""

from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path

logger = logging.getLogger("metatest")


class PluginContext:
    """提供给插件的注册 API。"""

    def register_python_operator(self, name: str, fn) -> None:
        from metatest.mutators.base import register_python_operator

        register_python_operator(name, fn)
        logger.info("插件注册 Python 变异算子: %s", name)

    def register_c_operator(self, name: str, fn) -> None:
        from metatest.mutators.base import register_c_operator

        register_c_operator(name, fn)
        logger.info("插件注册 C 变异算子: %s", name)

    def register_adapter(self, name: str, cls) -> None:
        from metatest.adapters import register_adapter

        register_adapter(name, cls)
        logger.info("插件注册适配器: %s", name)


def load_plugins(config=None, extra_dirs=()) -> list:
    """加载所有插件，返回已加载模块名列表。加载失败仅告警不致命。"""
    ctx = PluginContext()
    loaded = []
    # 1. entry points
    try:
        from importlib.metadata import entry_points

        eps = entry_points(group="metatest.plugins")
        for ep in eps:
            try:
                module = ep.load()
                if hasattr(module, "register"):
                    module.register(ctx)
                loaded.append(f"entry_point:{ep.name}")
            except Exception as e:
                logger.warning("加载插件 %s 失败: %s", ep.name, e)
    except Exception as e:
        logger.warning("扫描 entry point 插件失败: %s", e)

    # 2. 本地目录
    dirs = list(extra_dirs)
    if config is not None:
        dirs.extend(config.plugins.get("dirs") or [])
    for d in dirs:
        for module in _load_dir(Path(d)):
            try:
                if hasattr(module, "register"):
                    module.register(ctx)
                    loaded.append(f"dir:{getattr(module, '__name__', d)}")
                else:
                    logger.warning("插件 %s 未定义 register(ctx)，已跳过", d)
            except Exception as e:
                logger.warning("注册插件 %s 失败: %s", d, e)
    return loaded


def _load_dir(d: Path):
    """加载目录下的 .py 插件与包插件。"""
    if not d.exists():
        logger.warning("插件目录不存在: %s", d)
        return
    for path in sorted(d.iterdir()):
        if path.name.startswith("_") or path.name.startswith("."):
            continue
        if path.is_file() and path.suffix == ".py":
            yield _import_file(path)
        elif path.is_dir() and (path / "__init__.py").exists():
            yield _import_file(path / "__init__.py", module_name=f"mt_plugin_{path.name}")


def _import_file(path: Path, module_name: str | None = None):
    name = module_name or f"mt_plugin_{path.stem}_{abs(hash(str(path))) % 10000}"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module
