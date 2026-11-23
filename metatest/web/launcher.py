"""控制台启动器：`metatest ui` / `python -m metatest.web` / 打包后的 exe 共用入口。"""

from __future__ import annotations

import argparse
import socket
import sys


def _free_port(host: str, start: int = 8777) -> int:
    for port in range(start, start + 40):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((host, port))
            except OSError:
                continue
            return port
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="metatest-ui",
        description="MetaTest 本地控制台（浏览器界面）",
    )
    parser.add_argument("--host", default="127.0.0.1", help="监听地址（默认仅本机）")
    parser.add_argument("--port", type=int, default=0,
                        help="端口（默认自动选择，从 8777 起）")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    parser.add_argument("--project", default=None, help="启动后直接打开某个项目")
    parser.add_argument("--verbose", action="store_true", help="输出 HTTP 访问日志")
    args = parser.parse_args(argv)

    from metatest.web.server import serve

    port = args.port or _free_port(args.host)
    return serve(host=args.host, port=port, open_browser=not args.no_browser,
                 project=args.project, out=lambda m: print(m, flush=True))


if __name__ == "__main__":
    sys.exit(main())
