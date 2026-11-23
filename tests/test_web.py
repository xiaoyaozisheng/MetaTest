"""Web 控制台后端测试：API 契约、安全边界、任务链路与 SSE。

不依赖真实浏览器：直接对回环端口发 HTTP 请求，验证界面依赖的每个接口。
"""

from __future__ import annotations

import http.client
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

from metatest.web.server import create_server

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "examples" / "python_demo"


@pytest.fixture(scope="module")
def base_url():
    httpd = create_server("127.0.0.1", 0)
    thread = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.05},
                              daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def _request(base, path, method="GET", body=None, headers=None):
    url = base + path
    data = None
    hdrs = dict(headers or {})
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def get_json(base, path):
    status, raw = _request(base, path)
    assert status == 200, raw[:400]
    return json.loads(raw)


def post_json(base, path, body, client=True):
    headers = {"X-Metatest-Client": "web"} if client else {}
    status, raw = _request(base, path, method="POST", body=body, headers=headers)
    payload = json.loads(raw) if raw else None
    return status, payload


def wait_job(base, job_id, timeout=180):
    deadline = time.time() + timeout
    while time.time() < deadline:
        snap = get_json(base, f"/api/jobs/{job_id}")
        if snap["status"] in ("done", "failed"):
            return snap
        time.sleep(0.4)
    raise AssertionError(f"任务 {job_id} 超时未结束")


# ---------------------------------------------------------------------------
# 静态页面与元信息
# ---------------------------------------------------------------------------


class TestStaticAndMeta:
    def test_index_served(self, base_url):
        status, raw = _request(base_url, "/")
        assert status == 200
        html = raw.decode("utf-8")
        assert "MetaTest" in html and "/app.js" in html

    def test_unknown_path_falls_back_to_spa(self, base_url):
        status, raw = _request(base_url, "/some/deep/link")
        assert status == 200 and b"MetaTest" in raw

    def test_styles_and_script(self, base_url):
        for path, needle in (("/styles.css", b"--accent"), ("/app.js", b"I18N")):
            status, raw = _request(base_url, path)
            assert status == 200 and needle in raw

    def test_meta(self, base_url):
        data = get_json(base_url, "/api/meta")
        assert data["app"] == "MetaTest"
        assert data["version"]
        assert any(op["name"] == "relational" for op in data["operators"])

    def test_selftest_cases(self, base_url):
        data = get_json(base_url, "/api/selftest/cases")
        ids = {c["case_id"] for c in data["cases"]}
        assert {"py_must_fail", "py_skip", "c_mutant_kill"} <= ids


# ---------------------------------------------------------------------------
# 目录浏览与项目探测
# ---------------------------------------------------------------------------


class TestProjectApi:
    def test_browse_root(self, base_url):
        data = get_json(base_url, "/api/browse")
        assert Path(data["path"]).is_dir()
        assert isinstance(data["dirs"], list)

    def test_browse_specific_dir_marks_config(self, base_url, tmp_path):
        (tmp_path / "metatest.yaml").write_text("project: {name: x}\n", encoding="utf-8")
        (tmp_path / "sub").mkdir()
        data = get_json(base_url, "/api/browse?path=" + urllib.parse.quote(str(tmp_path.parent)))
        entry = next(d for d in data["dirs"] if d["path"] == str(tmp_path))
        assert entry["has_config"] is True

    def test_browse_missing_dir(self, base_url, tmp_path):
        status, payload = _request(base_url, "/api/browse?path=" + urllib.parse.quote(str(tmp_path / "nope")))
        assert status == 400 and "不存在" in payload.decode("utf-8")

    def test_project_info_demo(self, base_url):
        if not (DEMO / "metatest.yaml").exists():
            pytest.skip("示例项目缺少配置")
        data = get_json(base_url, "/api/project?path=" + urllib.parse.quote(str(DEMO)))
        assert data["name"] == "python_demo"
        assert data["language"] == "python"
        assert data["has_config"] is True
        assert data["config"]["test_cmd"]


class TestInitAndTrust:
    def test_init_creates_config_and_trust(self, base_url, tmp_path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "m.py").write_text("def f(a):\n    return a + 1\n", encoding="utf-8")
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_m.py").write_text(
            "from m import f\n\n\ndef test_f():\n    assert f(1) == 2\n", encoding="utf-8")
        status, info = post_json(base_url, "/api/project/init", {"path": str(tmp_path)})
        assert status == 200
        assert (tmp_path / "metatest.yaml").exists()
        assert info["has_config"] is True
        assert info["trusted"] is True, "init 应自动登记信任"

    def test_trust_and_revoke(self, base_url, tmp_path):
        cfg = tmp_path / "metatest.yaml"
        cfg.write_text(
            "project:\n  name: t\n  language: python\n  test_cmd: 'python -c \"print(1)\"'\n"
            "  source_roots: ['src']\n  test_roots: ['tests']\nreport: {formats: []}\n",
            encoding="utf-8")
        (tmp_path / "src").mkdir()
        (tmp_path / "tests").mkdir()

        info = get_json(base_url, "/api/project?path=" + urllib.parse.quote(str(tmp_path)))
        assert info["trusted"] is False, "仓库内容不能自我授权"

        status, info = post_json(base_url, "/api/project/trust", {"path": str(tmp_path)})
        assert status == 200 and info["trusted"] is True

        status, info = post_json(base_url, "/api/project/revoke", {"path": str(tmp_path)})
        assert status == 200 and info["trusted"] is False

    def test_config_save_invalidates_trust(self, base_url, tmp_path):
        cfg = tmp_path / "metatest.yaml"
        cfg.write_text("project: {name: a, language: python, test_cmd: 'python -c \"1\"',"
                       " source_roots: ['src'], test_roots: ['tests']}\n", encoding="utf-8")
        (tmp_path / "src").mkdir()
        (tmp_path / "tests").mkdir()
        post_json(base_url, "/api/project/trust", {"path": str(tmp_path)})

        new_text = cfg.read_text(encoding="utf-8") + "\n# changed\n"
        status, info = post_json(base_url, "/api/project/config",
                                 {"path": str(tmp_path), "text": new_text})
        assert status == 200
        assert info["trusted"] is False, "配置内容变化后信任应失效"

    def test_config_save_rejects_bad_yaml(self, base_url, tmp_path):
        cfg = tmp_path / "metatest.yaml"
        cfg.write_text("project: {name: a}\n", encoding="utf-8")
        status, payload = post_json(base_url, "/api/project/config",
                                    {"path": str(tmp_path), "text": "a: [unclosed"})
        assert status == 400
        assert "YAML" in payload["error"]


# ---------------------------------------------------------------------------
# 安全边界
# ---------------------------------------------------------------------------


class TestSecurity:
    def test_post_requires_client_header(self, base_url, tmp_path):
        status, payload = post_json(base_url, "/api/project/init", {"path": str(tmp_path)},
                                    client=False)
        assert status == 403

    def test_unknown_api_is_json_404(self, base_url):
        status, raw = _request(base_url, "/api/nope")
        assert status == 404 and json.loads(raw)["code"] == "not_found"

    def test_report_path_traversal_blocked(self, base_url, tmp_path):
        (tmp_path / ".metatest" / "report").mkdir(parents=True)
        (tmp_path / "secret.txt").write_text("top secret", encoding="utf-8")
        for name in ("../../secret.txt", "..%2F..%2Fsecret.txt"):
            status, raw = _request(
                base_url,
                "/api/report?path=" + urllib.parse.quote(str(tmp_path)) + "&file=" + name)
            assert status == 400, raw

    def test_invalid_host_header_rejected(self, base_url):
        port = base_url.rsplit(":", 1)[1]
        conn = http.client.HTTPConnection("127.0.0.1", int(port), timeout=10)
        conn.request("GET", "/api/meta", headers={"Host": "evil.example.com"})
        resp = conn.getresponse()
        assert resp.status == 403
        conn.close()


# ---------------------------------------------------------------------------
# 解释器探测与绑定（多 Python 环境下的关键体验）
# ---------------------------------------------------------------------------


class TestInterpreters:
    def test_list_and_assign(self, base_url, tmp_path):
        data = get_json(base_url, "/api/interpreters?path=" + urllib.parse.quote(str(tmp_path)))
        assert data["candidates"], "至少应探测到 MetaTest 自身解释器"
        assert any(c["pytest"] for c in data["candidates"]), "自身解释器应可用 pytest"

        target = next(c["path"] for c in data["candidates"] if c["pytest"])
        status, after = post_json(base_url, "/api/interpreters",
                                  {"path": str(tmp_path), "executable": target})
        assert status == 200
        assert after["assigned"] == str(Path(target).resolve())
        assert any(c["assigned"] for c in after["candidates"])

        status, cleared = post_json(base_url, "/api/interpreters",
                                    {"path": str(tmp_path), "executable": None})
        assert status == 200 and cleared["assigned"] is None

    def test_assign_missing_executable(self, base_url, tmp_path):
        status, payload = post_json(base_url, "/api/interpreters",
                                    {"path": str(tmp_path), "executable": str(tmp_path / "nope.exe")})
        assert status == 400


class TestBarePythonResolution:
    def test_bare_python_replaced(self):
        from metatest.adapters.python_adapter import resolve_python_command

        cmd = resolve_python_command("python -m pytest -q", executable="/usr/bin/python3")
        assert cmd.startswith("/usr/bin/python3 -m pytest")

    def test_absolute_path_untouched(self):
        from metatest.adapters.python_adapter import resolve_python_command

        original = 'C:////Python311////python.exe -m pytest'
        assert resolve_python_command(original, executable="/usr/bin/python3") == original


# ---------------------------------------------------------------------------
# 任务链路：变异评估 + SSE
# ---------------------------------------------------------------------------


class TestRunJob:
    @pytest.fixture
    def mini(self, tmp_path):
        files = {
            "src/maths.py": (
                "def add(a, b):\n    return a + b\n\n\n"
                "def is_positive(x):\n    return x > 0\n"
            ),
            "tests/test_m.py": (
                "from maths import add, is_positive\n\n\n"
                "def test_add():\n    assert add(1, 2) == 3\n\n\n"
                "def test_pos():\n    assert is_positive(1)\n    assert not is_positive(-1)\n"
            ),
            "conftest.py": (
                "import sys; from pathlib import Path\n"
                "sys.path.insert(0, str(Path(__file__).parent / 'src'))\n"
            ),
            "metatest.yaml": (
                "project:\n  name: webmini\n  language: python\n"
                "  test_cmd: 'python -m pytest -q'\n  test_result_format: junit_xml\n"
                "  source_roots: ['src']\n  test_roots: ['tests']\n"
                "  parallelism: 2\n  timeout_sec: 60\n"
                "mutation:\n  operators: ['arithmetic', 'relational']\n"
                "report:\n  formats: [json]\n  output_dir: .metatest/report\n"
                "quality_gate:\n  min_mutation_score: 0\n"
            ),
        }
        for rel, content in files.items():
            p = tmp_path / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
        return tmp_path

    def test_run_produces_results(self, base_url, mini):
        status, job = post_json(base_url, "/api/run", {
            "path": str(mini),
            "options": {"allow_commands": True, "no_quality": True, "parallel": 2,
                        "operators": "arithmetic,relational"},
        })
        assert status == 202, job
        snap = wait_job(base_url, job["id"])
        assert snap["status"] == "done"
        assert snap["exit_code"] in (0, 1), snap["logs"][-5:]
        result = snap["result"]
        assert result and result["results"], "应回传完整 results.json"
        summary = result["results"]["summary"]
        assert summary["total"] > 0
        assert summary["killed"] > 0
        assert (mini / ".metatest" / "report" / "results.json").exists()

    def test_sse_replays_logs_and_end(self, base_url, mini):
        status, job = post_json(base_url, "/api/run", {
            "path": str(mini),
            "options": {"allow_commands": True, "no_quality": True, "parallel": 2,
                        "operators": "arithmetic"},
        })
        assert status == 202
        wait_job(base_url, job["id"])
        port = int(base_url.rsplit(":", 1)[1])
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
        conn.request("GET", f"/api/jobs/{job['id']}/events?since=0")
        resp = conn.getresponse()
        assert resp.status == 200
        assert resp.getheader("Content-Type").startswith("text/event-stream")
        text = resp.read().decode("utf-8")
        conn.close()
        assert "event: log" in text
        assert "event: end" in text
        assert "[init]" in text

    def test_run_without_config_returns_409(self, base_url, tmp_path):
        status, payload = post_json(base_url, "/api/run", {"path": str(tmp_path), "options": {}})
        assert status == 409 and payload["code"] == "no_config"
