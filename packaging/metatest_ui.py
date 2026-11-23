"""PyInstaller 入口：打包后的 MetaTest 控制台（单文件 exe）。

构建：python scripts/build_exe.py
运行：MetaTest.exe [--port 8777] [--no-browser]
"""

from __future__ import annotations

import multiprocessing
import sys

from metatest.web.launcher import main

if __name__ == "__main__":
    # 打包后子进程（变异执行）需要 freeze_support，避免无限重入
    multiprocessing.freeze_support()
    sys.exit(main())
