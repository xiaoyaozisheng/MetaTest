"""一键打包 MetaTest 控制台为单文件可执行程序。

用法：
    python scripts/build_exe.py            # 构建 dist/MetaTest.exe
    python scripts/build_exe.py --onedir   # 目录模式（启动更快，便于调试）

依赖：pip install pyinstaller（本脚本会在缺失时提示安装命令）
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "packaging" / "MetaTest.spec"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--onedir", action="store_true", help="目录模式（默认单文件；spec 固定单文件时会忽略）")
    parser.add_argument("--keep-build", action="store_true", help="保留 build/ 中间目录")
    args = parser.parse_args()

    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("缺少 PyInstaller：\n    python -m pip install pyinstaller", file=sys.stderr)
        return 2

    # 图标（可选）
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from make_icon import build_icon

        if build_icon(ROOT / "packaging" / "metatest.ico"):
            print("[icon] packaging/metatest.ico")
    except Exception as e:  # 图标失败不影响打包
        print(f"[icon] 跳过: {e}")

    dist = ROOT / "dist"
    work = ROOT / "build"
    # 使用 .spec 时不要传 --onefile/--specpath（PyInstaller 会拒绝）
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--distpath", str(dist),
        "--workpath", str(work),
        str(SPEC),
    ]

    print("[build] " + " ".join(cmd))
    proc = subprocess.run(cmd, cwd=ROOT)
    if proc.returncode != 0:
        return proc.returncode

    if not args.keep_build:
        shutil.rmtree(work, ignore_errors=True)

    exe_name = "MetaTest.exe" if sys.platform == "win32" else "MetaTest"
    out = dist / exe_name
    if not out.exists() and (dist / "MetaTest" / exe_name).exists():
        out = dist / "MetaTest" / exe_name
    if out.exists():
        size_mb = out.stat().st_size / 1024 / 1024
        print(f"\n[done] {out}（{size_mb:.1f} MB）")
        print(f"       双击运行，或命令行：\"{out}\" --port 8777")
        return 0
    print("[done] 构建结束，但未找到产物，请检查上方日志", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
