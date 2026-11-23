# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 配置：MetaTest 控制台（Windows / macOS / Linux 通用）。

打包内容：
  * metatest 包全部子模块
  * 前端静态资源 metatest/web/static
  * 元测试基准项目库 metatest/metatests（自检必须）
  * 插件模板 metatest/plugins/templates
可选依赖（tree-sitter / coverage / pytest-cov）安装时自动打进去。
"""

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).parent
PACKAGE = ROOT / "metatest"

datas = [
    (str(PACKAGE / "web" / "static"), "metatest/web/static"),
    (str(PACKAGE / "metatests"), "metatest/metatests"),
    (str(PACKAGE / "plugins" / "templates"), "metatest/plugins/templates"),
]

hiddenimports = collect_submodules("metatest")
for optional in ("yaml", "tree_sitter", "tree_sitter_c", "coverage", "pytest_cov"):
    try:
        __import__(optional)
    except Exception:
        continue
    hiddenimports.append(optional)
    if optional.startswith("tree_sitter"):
        hiddenimports.extend(collect_submodules(optional))

icon = ROOT / "packaging" / "metatest.ico"

a = Analysis(
    [str(ROOT / "packaging" / "metatest_ui.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=sorted(set(hiddenimports)),
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "pandas", "PySide6", "PyQt5", "IPython"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="MetaTest",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    icon=str(icon) if icon.exists() else None,
)
