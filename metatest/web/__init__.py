"""本地 Web 控制台：浏览器界面 + 仅回环监听的 HTTP API（标准库实现）。

对 CLI 的封装，不改变任何判定语义：
  * 变异评估 / 质量分析 / 元测试自检均在后台线程中调用既有 CLI 入口；
  * 日志以 SSE 实时推送到前端，结果复用 .metatest/report/results.json。
"""

from metatest.web.server import create_server, serve

__all__ = ["create_server", "serve"]
