"""本地 HTTP 服务：静态页面 + JSON API + SSE 日志流（仅标准库）。

安全边界（本地单用户工具）：
  * 默认只监听 127.0.0.1，并校验 Host 头（防 DNS rebinding）；
  * 所有写操作要求自定义请求头 X-Metatest-Client（浏览器跨站表单无法伪造）；
  * 报告文件读取限制在项目 .metatest/report 目录内；
  * 是否执行配置里的命令仍由 CLI 的信任模型决定（前端需二次确认）。
"""

from __future__ import annotations

import json
import mimetypes
import re
import socket
import sys
import threading
import time
import traceback
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from metatest.errors import MetaTestError
from metatest.web import api
from metatest.web.jobs import JobManager
from metatest.web.paths import static_dir

MAX_BODY = 1 << 20  # 1 MiB：配置文本/选项足够
CLIENT_HEADER = "X-Metatest-Client"
_JOB_RE = re.compile(r"^/api/jobs/([0-9a-f]{6,})$")
_EVENTS_RE = re.compile(r"^/api/jobs/([0-9a-f]{6,})/events$")
STATIC_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
    ".woff2": "font/woff2",
    ".png": "image/png",
    ".ico": "image/x-icon",
}


class ApiError(Exception):
    def __init__(self, message: str, status: int = 400, code: str = "bad_request"):
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code


class Handler(BaseHTTPRequestHandler):
    server_version = "MetaTestWeb/1.0"
    protocol_version = "HTTP/1.1"
    jobs: JobManager = None  # type: ignore[assignment]

    # -- 基础 -----------------------------------------------------------

    def log_message(self, fmt, *args):  # 静音 HTTP 访问日志（CLI 日志已足够）
        if getattr(self.server, "verbose", False):
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _allowed_host(self) -> bool:
        host = (self.headers.get("Host") or "").split(":")[0].strip().lower()
        return host in ("127.0.0.1", "localhost", "::1", "[::1]")

    def _send(self, status: int, body: bytes, ctype: str, extra: dict | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, payload, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8")

    def _error(self, err: ApiError) -> None:
        self._json({"error": err.message, "code": err.code}, err.status)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if self.headers.get(CLIENT_HEADER) is None:
            # 先把请求体读掉，避免 keep-alive 连接里残留数据导致客户端收到 RST
            if length and length <= MAX_BODY:
                self.rfile.read(length)
            raise ApiError("缺少请求头：仅本控制台页面可调用该接口", 403, "forbidden")
        if length > MAX_BODY:
            raise ApiError("请求体过大", 413, "too_large")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError) as e:
            raise ApiError(f"请求体不是合法 JSON: {e}") from e
        if not isinstance(data, dict):
            raise ApiError("请求体必须是 JSON 对象")
        return data

    # -- 路由 -----------------------------------------------------------

    def do_GET(self):
        try:
            if not self._allowed_host():
                raise ApiError("非法的 Host 头（仅允许本机访问）", 403, "forbidden")
            parsed = urlparse(self.path)
            query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
            path = unquote(parsed.path)
            if path.startswith("/api/"):
                self._route_get(path, query)
            else:
                self._serve_static(path)
        except ApiError as e:
            self._error(e)
        except MetaTestError as e:
            self._error(ApiError(str(e), 400, "bad_request"))
        except BrokenPipeError:
            pass
        except Exception as e:  # 兜底：接口异常不拖垮服务
            self._json({"error": f"内部错误: {e}", "code": "internal",
                        "trace": traceback.format_exc(limit=3)}, 500)

    def do_HEAD(self):
        self.do_GET()

    def do_POST(self):
        try:
            if not self._allowed_host():
                raise ApiError("非法的 Host 头（仅允许本机访问）", 403, "forbidden")
            parsed = urlparse(self.path)
            body = self._read_json()
            self._route_post(unquote(parsed.path), body)
        except ApiError as e:
            self._error(e)
        except MetaTestError as e:
            self._error(ApiError(str(e), 400, "bad_request"))
        except BrokenPipeError:
            pass
        except Exception as e:
            self._json({"error": f"内部错误: {e}", "code": "internal",
                        "trace": traceback.format_exc(limit=3)}, 500)

    # -- GET 处理 --------------------------------------------------------

    def _route_get(self, path: str, query: dict) -> None:
        if path == "/api/meta":
            self._json(api.meta_info())
            return
        if path == "/api/browse":
            self._json(api.browse(query.get("path")))
            return
        if path == "/api/project":
            p = query.get("path")
            if not p:
                raise ApiError("缺少 path 参数")
            info = api.project_info(p)
            api.remember_project(info["path"])
            self._json(info)
            return
        if path == "/api/report":
            root = query.get("path")
            name = query.get("file", "report.html")
            if not root:
                raise ApiError("缺少 path 参数")
            target = api.report_file(Path(root), name)
            ctype = STATIC_TYPES.get(target.suffix.lower()) or mimetypes.guess_type(str(target))[0] \
                or "application/octet-stream"
            self._send(200, target.read_bytes(), ctype)
            return
        if path == "/api/jobs":
            self._json({"jobs": self.jobs.list()})
            return
        m = _EVENTS_RE.match(path)
        if m:
            self._stream_events(m.group(1), int(query.get("since") or 0))
            return
        m = _JOB_RE.match(path)
        if m:
            job = self.jobs.get(m.group(1))
            if job is None:
                raise ApiError("任务不存在", 404, "not_found")
            self._json(job.snapshot(int(query.get("since") or 0)))
            return
        if path == "/api/selftest/cases":
            self._json({"cases": api.selftest_cases()})
            return
        if path == "/api/interpreters":
            project = query.get("path")
            if not project:
                raise ApiError("缺少 path 参数")
            self._json(api.interpreters(project))
            return
        if path == "/api/selftest/last":
            self._json({"result": api.last_selftest()})
            return
        raise ApiError(f"未知接口: {path}", 404, "not_found")

    # -- POST 处理 -------------------------------------------------------

    def _route_post(self, path: str, body: dict) -> None:
        if path == "/api/project/open":
            project = body.get("path")
            if not project:
                raise ApiError("缺少 path")
            info = api.project_info(project)
            api.remember_project(info["path"])
            self._json(info)
            return
        if path == "/api/project/init":
            project = body.get("path")
            if not project:
                raise ApiError("缺少 path")
            self._json(api.init_project(project, body.get("language"), bool(body.get("force"))))
            return
        if path == "/api/project/trust":
            self._json(api.trust_project(body.get("path") or ""))
            return
        if path == "/api/project/revoke":
            self._json(api.revoke_project(body.get("path") or ""))
            return
        if path == "/api/interpreters":
            self._json(api.assign_interpreter(body.get("path") or "", body.get("executable")))
            return
        if path == "/api/project/config":
            self._json(api.save_config(body.get("path") or "", body.get("text") or ""))
            return
        if path == "/api/run":
            root = Path(body.get("path") or "").expanduser().resolve()
            if not (root / "metatest.yaml").exists():
                raise ApiError("该项目尚无 metatest.yaml，请先在「项目」页初始化", 409, "no_config")
            opts = body.get("options") or {}
            argv, report_dir = api.build_run_argv(root, opts)
            job = self.jobs.submit(
                kind="run",
                argv=argv,
                title=f"变异评估 · {root.name}",
                project=str(root),
                meta={"report_dir": report_dir, "options": opts},
                collector=api.run_collector(report_dir),
            )
            self._json(job.summary(), 202)
            return
        if path == "/api/quality":
            root = Path(body.get("path") or "").expanduser().resolve()
            if not (root / "metatest.yaml").exists():
                raise ApiError("该项目尚无 metatest.yaml", 409, "no_config")
            out = root / ".metatest" / "report" / "quality.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            argv = api.build_quality_argv(root, out, bool(body.get("flaky")))
            job = self.jobs.submit(
                kind="quality",
                argv=argv,
                title=f"质量分析 · {root.name}",
                project=str(root),
                meta={},
                collector=api.quality_collector(out),
            )
            self._json(job.summary(), 202)
            return
        if path == "/api/selftest":
            out = Path.home() / ".metatest" / "selftest_last.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            argv = api.build_selftest_argv(out, body.get("cases") or None)
            job = self.jobs.submit(
                kind="selftest",
                argv=argv,
                title="元测试自检",
                project=None,
                meta={},
                collector=api.selftest_collector(out),
            )
            self._json(job.summary(), 202)
            return
        raise ApiError(f"未知接口: {path}", 404, "not_found")

    # -- SSE ------------------------------------------------------------

    def _stream_events(self, job_id: str, since: int) -> None:
        job = self.jobs.get(job_id)
        if job is None:
            raise ApiError("任务不存在", 404, "not_found")
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-transform")
        self.send_header("Connection", "close")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        self.close_connection = True

        def emit(event: str, payload) -> None:
            data = json.dumps(payload, ensure_ascii=False, default=str)
            self.wfile.write(f"event: {event}\ndata: {data}\n\n".encode("utf-8"))
            self.wfile.flush()

        try:
            cursor = since
            emit("state", job.summary())
            while True:
                logs, terminal = job.wait_for_logs(cursor, timeout=15)
                if logs:
                    emit("log", logs)
                    cursor = logs[-1]["i"] + 1
                emit("state", job.summary())
                if terminal and not logs:
                    emit("end", job.snapshot(cursor, with_result=True))
                    break
                if not logs:
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            return

    # -- 静态资源 --------------------------------------------------------

    def _serve_static(self, path: str) -> None:
        base = static_dir()
        rel = "index.html" if path in ("/", "") else path.lstrip("/")
        if rel.startswith("static/"):
            rel = rel[len("static/"):]
        target = (base / rel).resolve()
        if not str(target).startswith(str(base.resolve())) or not target.is_file():
            # 单页应用：未知路径回落到 index.html（保留前端路由能力）
            target = base / "index.html"
            if not target.is_file():
                raise ApiError("前端资源缺失（安装包可能不完整）", 500, "no_static")
        ctype = STATIC_TYPES.get(target.suffix.lower()) or "application/octet-stream"
        self._send(200, target.read_bytes(), ctype)


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def handle_error(self, request, client_address):
        # 浏览器关闭 SSE / 刷新页面会产生连接重置，属正常现象，不打印堆栈
        exc = sys.exc_info()[1]
        if isinstance(exc, (ConnectionResetError, ConnectionAbortedError, BrokenPipeError)):
            return
        super().handle_error(request, client_address)


def _pick_port(host: str, port: int) -> int:
    if port:
        return port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        return s.getsockname()[1]


def create_server(host: str = "127.0.0.1", port: int = 0, verbose: bool = False,
                  job_manager: JobManager | None = None) -> Server:
    port = _pick_port(host, port)
    handler = type("BoundHandler", (Handler,), {"jobs": job_manager or JobManager()})
    httpd = Server((host, port), handler)
    httpd.verbose = verbose
    return httpd


def serve(host: str = "127.0.0.1", port: int = 0, open_browser: bool = True,
          project: str | None = None, out=None) -> int:
    out = out or (lambda msg: print(msg, flush=True))
    httpd = create_server(host, port)
    actual_port = httpd.server_address[1]
    url = f"http://{'127.0.0.1' if host in ('0.0.0.0', '::') else host}:{actual_port}/"
    if project:
        url += f"?project={project}"
    out("=" * 62)
    out(f"MetaTest 控制台已启动: {url}")
    out("仅监听本机回环地址；关闭此窗口或按 Ctrl+C 退出。")
    out("=" * 62)
    if open_browser:
        def _open():
            time.sleep(0.6)
            try:
                webbrowser.open(url)
            except Exception:
                pass

        threading.Thread(target=_open, daemon=True).start()
    try:
        httpd.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        out("\n[ui] 已停止")
    finally:
        httpd.shutdown()
        httpd.server_close()
    return 0
