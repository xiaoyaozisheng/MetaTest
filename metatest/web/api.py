"""Web 控制台的数据层：项目探测、目录浏览、命令组装、结果读取。

所有判定语义都来自既有 CLI / 引擎；这一层只做"给界面用的视角"。
"""

from __future__ import annotations

import json
import os
import string
import sys
import time
from pathlib import Path

from metatest.adapters import detect_language
from metatest.config import (
    CONFIG_FILE_NAME,
    OPERATORS,
    commands_allowed,
    config_fingerprint,
    grant_trust,
    load_config,
    revoke_trust,
)
from metatest.errors import MetaTestError

SKIP_DIRS = {
    ".git", ".hg", ".svn", "__pycache__", "node_modules", "venv", ".venv", "env",
    ".idea", ".vscode", ".pytest_cache", ".mypy_cache", ".ruff_cache", "dist", "build",
    ".next", ".gradle", ".cache", "target", "out", "cmake-build-debug", "cmake-build-release",
}
MAX_ENTRIES = 400


# ---------------------------------------------------------------------------
# 用户级状态（最近打开的项目）
# ---------------------------------------------------------------------------


def state_path() -> Path:
    return Path.home() / ".metatest" / "web_state.json"


def load_state() -> dict:
    p = state_path()
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"recent": []}


def save_state(state: dict) -> None:
    p = state_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def _is_transient(path) -> bool:
    """临时目录（pytest 的 tmp_path 等）不作为"最近项目"记忆。"""
    import tempfile

    try:
        root = Path(path).resolve()
        tmp = Path(tempfile.gettempdir()).resolve()
        return root == tmp or tmp in root.parents
    except (OSError, ValueError):
        return True


def remember_project(path: str) -> None:
    if _is_transient(path):
        return
    state = load_state()
    recent = [p for p in state.get("recent", []) if Path(p) != Path(path)]
    recent.insert(0, str(Path(path)))
    state["recent"] = recent[:12]
    state["last_project"] = str(Path(path))
    save_state(state)


# ---------------------------------------------------------------------------
# 元信息
# ---------------------------------------------------------------------------


def meta_info() -> dict:
    from metatest import __version__

    state = load_state()
    return {
        "app": "MetaTest",
        "version": __version__,
        "python": sys.version.split()[0],
        "executable": sys.executable,
        "platform": sys.platform,
        "frozen": bool(getattr(sys, "frozen", False)),
        "cwd": os.getcwd(),
        "home": str(Path.home()),
        "operators": [{"name": k, "desc": v} for k, v in OPERATORS.items()],
        "recent": [p for p in state.get("recent", [])
                   if Path(p).exists() and not _is_transient(p)],
        "last_project": (state.get("last_project")
                         if state.get("last_project") and Path(state["last_project"]).exists()
                         and not _is_transient(state["last_project"]) else None),
        "report_dir_name": ".metatest/report",
    }


# ---------------------------------------------------------------------------
# 目录浏览 / 项目探测
# ---------------------------------------------------------------------------


def _looks_like_project(path: Path) -> dict:
    """零成本启发：目录里有什么（用于浏览列表打标）。"""
    has_cfg = (path / CONFIG_FILE_NAME).exists()
    hints = []
    if (path / "pyproject.toml").exists() or (path / "setup.py").exists():
        hints.append("python")
    if list(path.glob("*.py")) or (path / "src").is_dir():
        hints.append("python")
    if (path / "CMakeLists.txt").exists() or (path / "Makefile").exists():
        hints.append("c")
    if list(path.glob("*.c")):
        hints.append("c")
    return {"has_config": has_cfg, "hints": sorted(set(hints))}


def browse(path: str | None) -> dict:
    if path:
        target = Path(path).expanduser()
    else:
        target = Path.home()
    if not target.is_absolute():
        target = (Path.cwd() / target).resolve()
    if not target.exists() or not target.is_dir():
        raise MetaTestError(f"目录不存在: {target}")

    dirs = []
    try:
        entries = sorted(target.iterdir(), key=lambda p: p.name.lower())
    except PermissionError as e:
        raise MetaTestError(f"无权限访问: {target}") from e
    for entry in entries:
        if len(dirs) >= MAX_ENTRIES:
            break
        if not entry.is_dir():
            continue
        if entry.name.startswith(".") or entry.name in SKIP_DIRS:
            continue
        try:
            if entry.name.startswith("$") or entry.name in ("System Volume Information",):
                continue
            tag = _looks_like_project(entry)
        except OSError:
            continue
        dirs.append({
            "name": entry.name,
            "path": str(entry),
            "has_config": tag["has_config"],
            "hints": tag["hints"],
        })

    parent = str(target.parent) if target.parent != target else None
    roots = []
    if sys.platform == "win32" and parent is None:
        roots = [f"{d}:\\" for d in string.ascii_uppercase if Path(f"{d}:\\").exists()]
    return {"path": str(target), "parent": parent, "dirs": dirs, "roots": roots}


def project_info(path: str) -> dict:
    root = Path(path).expanduser()
    if not root.exists() or not root.is_dir():
        raise MetaTestError(f"项目目录不存在: {root}")
    root = root.resolve()
    cfg_path = root / CONFIG_FILE_NAME
    info = {
        "path": str(root),
        "name": root.name,
        "has_config": cfg_path.exists(),
        "config_path": str(cfg_path) if cfg_path.exists() else None,
        "language": detect_language(root),
        "trusted": False,
        "config_error": None,
        "config": None,
        "config_text": None,
        "last_report": None,
        "report_dir": str(root / ".metatest" / "report"),
        "has_git": (root / ".git").exists(),
    }
    if cfg_path.exists():
        try:
            info["config_text"] = cfg_path.read_text(encoding="utf-8")
        except OSError:
            pass
        try:
            cfg = load_config(cfg_path, project_root=root)
            info["config"] = {
                "name": cfg.name,
                "language": cfg.language,
                "build_cmd": cfg.build_cmd,
                "test_cmd": cfg.test_cmd,
                "test_result_format": cfg.test_result_format,
                "source_roots": cfg.source_roots,
                "test_roots": cfg.test_roots,
                "parallelism": cfg.parallelism,
                "timeout_sec": cfg.timeout_sec,
                "operators": cfg.effective_operators(),
                "incremental": cfg.mutation.incremental,
                "test_selection": cfg.mutation.test_selection,
                "min_mutation_score": cfg.quality_gate.min_mutation_score,
                "flaky_enabled": cfg.flaky.enabled,
                "report_formats": list(cfg.report.formats),
                "fingerprint": config_fingerprint(cfg_path)[:12],
            }
            info["language"] = cfg.language
            info["trusted"] = commands_allowed(cfg, False)
            info["report_dir"] = str(root / cfg.report.output_dir)
        except Exception as e:  # 配置写错时也要能在界面上看到原因
            info["config_error"] = str(e)

        last = _read_results(Path(info["report_dir"]))
        if last:
            info["last_report"] = last
    return info


def _read_results(report_dir: Path) -> dict | None:
    p = Path(report_dir) / "results.json"
    if not p.exists():
        return None
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    summary = doc.get("summary", {})
    return {
        "generated_at": doc.get("generated_at"),
        "mtime": p.stat().st_mtime,
        "score": summary.get("mutation_score_percent"),
        "total": summary.get("total"),
        "killed": summary.get("killed"),
        "survived": summary.get("survived"),
        "error": summary.get("error"),
        "duration_sec": summary.get("duration_sec"),
        "gate": doc.get("gate"),
        "paths": {name: str(Path(report_dir) / f) for name, f in (
            ("json", "results.json"), ("html", "report.html"), ("junit", "mutation_junit.xml")
        ) if (Path(report_dir) / f).exists()},
    }


# ---------------------------------------------------------------------------
# 初始化 / 信任 / 配置写入
# ---------------------------------------------------------------------------


def init_project(path: str, language: str | None = None, force: bool = False) -> dict:
    from metatest.cli.main import main as cli_main

    root = Path(path).expanduser().resolve()
    argv = ["init", str(root)]
    if language:
        argv += ["--language", language]
    if force:
        argv.append("--force")
    rc = cli_main(argv)
    info = project_info(str(root))
    info["exit_code"] = rc
    if rc == 0:
        remember_project(str(root))
    return info


def trust_project(path: str) -> dict:
    from metatest.cli.main import main as cli_main

    root = Path(path).expanduser().resolve()
    cfg_path = root / CONFIG_FILE_NAME
    if not cfg_path.exists():
        raise MetaTestError("配置不存在，先执行初始化")
    rc = cli_main(["allow", "--config", str(cfg_path), "--project-root", str(root)])
    info = project_info(str(root))
    info["exit_code"] = rc
    return info


def revoke_project(path: str) -> dict:
    from metatest.cli.main import main as cli_main

    root = Path(path).expanduser().resolve()
    cfg_path = root / CONFIG_FILE_NAME
    cli_main(["deny", "--config", str(cfg_path), "--project-root", str(root)])
    return project_info(str(root))


def save_config(path: str, text: str) -> dict:
    root = Path(path).expanduser().resolve()
    cfg_path = root / CONFIG_FILE_NAME
    if not cfg_path.exists():
        raise MetaTestError("配置不存在，先执行初始化")
    # 先验证 YAML 可解析，避免把项目写坏
    import yaml

    try:
        yaml.safe_load(text or "")
    except yaml.YAMLError as e:
        raise MetaTestError(f"YAML 解析失败: {e}") from e
    cfg_path.write_text(text, encoding="utf-8")
    info = project_info(str(root))
    # 内容变化 → 指纹失效 → 必须重新确认（与 CLI 安全模型一致）
    return info


# ---------------------------------------------------------------------------
# 命令组装 / 结果收集
# ---------------------------------------------------------------------------


def _as_int(value, default=None):
    try:
        if value in (None, ""):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value, default=None):
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _opt(opts: dict, *names, default=None):
    """同时接受 snake_case（CLI/脚本）与 camelCase（前端）键名。"""
    for name in names:
        if name in opts and opts[name] not in (None, ""):
            return opts[name]
    return default


def build_run_argv(root: Path, opts: dict) -> tuple[list, str]:
    cfg_path = root / CONFIG_FILE_NAME
    report_dir = root / ".metatest" / "report"
    argv = [
        "run",
        "--config", str(cfg_path),
        "--project-root", str(root),
        "--output-dir", str(report_dir),
    ]
    if _opt(opts, "allow_commands", "allowCommands"):
        argv.append("--allow-commands")
    if _opt(opts, "incremental"):
        argv.append("--incremental")
        diff_ref = _opt(opts, "diff_ref", "diffRef")
        if diff_ref:
            argv += ["--diff-ref", str(diff_ref)]
    parallel = _as_int(_opt(opts, "parallel"))
    if parallel:
        argv += ["--parallel", str(parallel)]
    timeout = _as_float(_opt(opts, "timeout"))
    if timeout:
        argv += ["--timeout", str(timeout)]
    if _opt(opts, "test_selection", "testSelection"):
        argv.append("--test-selection")
    if _opt(opts, "no_quality", "noQuality"):
        argv.append("--no-quality")
    if _opt(opts, "no_cache", "noCache"):
        argv.append("--no-cache")
    if _opt(opts, "flaky"):
        argv.append("--flaky")
    operators = str(_opt(opts, "operators", default="") or "").strip()
    if operators:
        argv += ["--operators", operators]
    exclude = str(_opt(opts, "exclude_operators", "excludeOperators", default="") or "").strip()
    if exclude:
        argv += ["--exclude-operators", exclude]
    return argv, str(report_dir)


def run_collector(report_dir: str):
    def _collect(job):
        doc = _read_results(Path(report_dir))
        results_path = Path(report_dir) / "results.json"
        full = None
        if results_path.exists():
            try:
                full = json.loads(results_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                full = None
        return {"summary": doc, "results": full}
    return _collect


def build_selftest_argv(out_file: Path, cases: list | None = None) -> list:
    argv = ["selftest", "--json", str(out_file)]
    for case in cases or []:
        argv += ["--case", case]
    return argv


def selftest_collector(out_file: Path):
    def _collect(job):
        try:
            return json.loads(Path(out_file).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
    return _collect


def build_quality_argv(root: Path, out_file: Path, flaky: bool = False) -> list:
    argv = [
        "quality",
        "--config", str(root / CONFIG_FILE_NAME),
        "--project-root", str(root),
        "--json", str(out_file),
    ]
    if flaky:
        argv.append("--flaky")
    return argv


def quality_collector(out_file: Path):
    def _collect(job):
        try:
            return json.loads(Path(out_file).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
    return _collect


def report_file(root: Path, name: str) -> Path:
    """只允许读取项目报告目录内的文件（防止路径穿越）。"""
    base = (root / ".metatest" / "report").resolve()
    target = (base / name).resolve()
    if not str(target).startswith(str(base)) or not target.is_file():
        raise MetaTestError("报告文件不存在")
    return target


def last_selftest() -> dict | None:
    p = Path.home() / ".metatest" / "selftest_last.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def interpreters(path: str) -> dict:
    """该项目的候选解释器与当前绑定（打包版常见坑：PATH 上的 python 没有 pytest）。"""
    from metatest.adapters.python_adapter import available_interpreters
    from metatest.interp_store import get_assigned

    root = Path(path).expanduser().resolve()
    if not root.is_dir():
        raise MetaTestError(f"项目目录不存在: {root}")
    return {
        "path": str(root),
        "assigned": get_assigned(root),
        "candidates": available_interpreters(root),
    }


def assign_interpreter(path: str, executable: str | None) -> dict:
    from metatest.interp_store import assign, clear

    root = Path(path).expanduser().resolve()
    if not root.is_dir():
        raise MetaTestError(f"项目目录不存在: {root}")
    if not executable:
        clear(root)
    else:
        try:
            assign(root, executable)
        except FileNotFoundError as e:
            raise MetaTestError(str(e)) from e
    return interpreters(str(root))


def selftest_cases() -> list:
    from metatest.selftest.runner import discover_cases

    cases = discover_cases(None)
    return [
        {"case_id": c.case_id, "kind": c.kind, "description": c.description}
        for c in cases
    ]


def now_iso() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")
