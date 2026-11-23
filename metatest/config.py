"""metatest.yaml 配置加载与校验（PRD FR-01）。

支持 CI 环境变量覆盖：
  METATEST_TEST_CMD        覆盖 test_cmd
  METATEST_BUILD_CMD       覆盖 build_cmd
  METATEST_PARALLELISM     覆盖 parallelism
  METATEST_TIMEOUT_SEC     覆盖 timeout_sec
  METATEST_OUTPUT_DIR      覆盖 report.output_dir
  METATEST_ALLOW_COMMANDS  显式允许执行配置中的命令（安全边界，见 README 安全章节）
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from metatest.errors import ConfigError

CONFIG_FILE_NAME = "metatest.yaml"

# ---------------------------------------------------------------------------
# 变异算子注册表（Python / C 共享算子语义定义，PRD 附录 12）
# ---------------------------------------------------------------------------

OPERATORS = {
    "relational": "关系运算符替换：> ↔ >=、< ↔ <=、== ↔ !=",
    "arithmetic": "算术运算符替换：+ ↔ -、* ↔ /",
    "boolean_negation": "布尔取反：not/! 移除、True/False 翻转、&& ↔ ||",
    "return_value": "返回值替换：return expr → return None/0",
    "statement_deletion": "删除语句：删除赋值/表达式语句",
    "boundary_value": "边界值修改：比较中的整数常量 +1",
    "condition_constant": "条件常量替换：if/三元条件 → True/False",
    "none_replacement": "None/空指针替换：调用实参 → None/NULL",
    "exception_removal": "异常删除：raise → pass、吞异常 → 再抛出",
    "loop_condition": "循环条件修改：while/for 条件 → False/0、range 缩短",
}

OPERATOR_ALIASES = {
    "boolean": "boolean_negation",
    "bool": "boolean_negation",
    "boundary": "boundary_value",
    "condition": "condition_constant",
    "none": "none_replacement",
    "null_replacement": "none_replacement",
    "exception": "exception_removal",
    "loop": "loop_condition",
    "statement": "statement_deletion",
    "return": "return_value",
}


def normalize_operators(raw, strict: bool = True) -> list:
    """把配置中的算子列表/别名规范化为标准算子名列表。

    插件注册的算子（register_python_operator / register_c_operator / 规则化算子）
    合法可用。strict=False（配置文件加载路径）时未知算子保留原样并告警——
    因为插件在配置加载之后才载入，此时无法判定其合法性；
    strict=True（CLI --operators）时未知算子直接报错。
    """
    if raw is None:
        return list(OPERATORS)
    if isinstance(raw, str):
        raw = [raw]
    import logging

    logger = logging.getLogger("metatest")
    result = []
    for item in raw:
        name = OPERATOR_ALIASES.get(str(item).strip(), str(item).strip())
        if name == "all":
            return list(OPERATORS)
        if name not in OPERATORS:
            # 插件/规则算子：加载后由 mutator 按名调用；加载前无法判定
            if strict:
                from metatest.mutators.base import custom_c_operators, custom_python_operators

                if name not in custom_python_operators() and name not in custom_c_operators():
                    raise ConfigError(
                        f"未知变异算子: {item!r}。可用算子: {', '.join(OPERATORS)}"
                        f"（别名: {', '.join(sorted(OPERATOR_ALIASES))} 或 'all'；"
                        "插件/规则算子在插件加载后可用）"
                    )
            else:
                logger.warning(
                    "算子 %r 不是内置算子：若为插件/规则算子将在插件加载后生效，否则将被忽略", item)
        if name not in result:
            result.append(name)
    return result


# ---------------------------------------------------------------------------
# 配置数据类
# ---------------------------------------------------------------------------


@dataclass
class MutationOptions:
    operators: list = field(default_factory=lambda: list(OPERATORS))
    exclude_operators: list = field(default_factory=list)
    incremental: bool = False
    exclude_globs: list = field(default_factory=list)   # 源码文件排除模式（fnmatch）
    include_globs: list = field(default_factory=list)   # 为空表示全部
    fail_fast: bool = False                             # 测试失败时尽早终止该变异体的测试运行
    test_selection: bool = False                        # 测试关联筛选：只运行覆盖变异行的测试
    strategy: str = "auto"                              # 变异策略：auto / ast / tree_sitter / fallback / llvm_ir
    rule_files: list = field(default_factory=list)      # 规则化变异（universalmutator 思路）：YAML 规则文件列表


@dataclass
class QualityGateOptions:
    enabled: bool = True
    min_mutation_score: Optional[float] = None   # 0-100 百分数
    max_flaky: Optional[int] = None              # 允许的 flaky 测试数上限
    max_weak_assertions: Optional[int] = None
    fail_on_survived: bool = False               # 存在 survived 即失败


@dataclass
class FlakyOptions:
    runs: int = 3
    enabled: bool = True
    isolate: bool = False   # 对 flaky 测试单独复跑分类（isolated_flaky / order_dependent）


@dataclass
class CacheOptions:
    enabled: bool = True
    dir: str = ".metatest"


@dataclass
class SandboxOptions:
    copy_exclude: list = field(default_factory=list)


@dataclass
class ReportOptions:
    formats: list = field(default_factory=lambda: ["html", "json", "junit_xml"])
    output_dir: str = ".metatest/report"


@dataclass
class ProjectConfig:
    """PRD ProjectConfig 实体。"""

    name: str = "unnamed"
    language: str = "python"
    build_cmd: str = ""
    test_cmd: str = ""
    test_result_format: str = "junit_xml"     # junit_xml | exit_code
    source_roots: list = field(default_factory=lambda: ["src"])
    test_roots: list = field(default_factory=lambda: ["tests"])
    parallelism: int = 4
    timeout_sec: float = 120.0
    env: dict = field(default_factory=dict)   # 传递给测试命令的附加环境变量
    mutation: MutationOptions = field(default_factory=MutationOptions)
    quality_gate: QualityGateOptions = field(default_factory=QualityGateOptions)
    flaky: FlakyOptions = field(default_factory=FlakyOptions)
    cache: CacheOptions = field(default_factory=CacheOptions)
    sandbox: SandboxOptions = field(default_factory=SandboxOptions)
    report: ReportOptions = field(default_factory=ReportOptions)
    adapter: dict = field(default_factory=dict)  # 语言适配器专属选项
    plugins: dict = field(default_factory=dict)  # {"dirs": [...]}
    trust: bool = False                          # init 生成的配置视为可信
    junit_path: Optional[str] = None             # 结果文件路径（相对项目根，默认自动推断）
    config_path: Optional[str] = None            # 配置文件所在路径（加载后回填）
    project_root: Optional[str] = None           # 项目根目录（默认配置文件所在目录）

    # -- 校验 ------------------------------------------------------------

    def validate(self) -> None:
        problems = []
        if not self.name or not isinstance(self.name, str):
            problems.append("project.name 必须是非空字符串")
        if self.language not in ("python", "c", "command"):
            problems.append(
                f"project.language 必须是 python/c/command（当前: {self.language!r}）；"
                "其他语言请使用 command 适配器接入"
            )
        if not self.test_cmd or not isinstance(self.test_cmd, str):
            # C 项目允许省略 test_cmd：使用 adapter.test_binary 或 CMake/ctest
            if not (self.language == "c" and self.adapter.get("test_binary")):
                problems.append("project.test_cmd 必须是非空字符串（C 项目可用 adapter.test_binary 替代）")
        if self.test_result_format not in ("junit_xml", "exit_code"):
            problems.append("project.test_result_format 必须是 junit_xml 或 exit_code")
        if self.language in ("python", "c"):
            if not self.source_roots or not all(isinstance(r, str) and r for r in self.source_roots):
                problems.append("project.source_roots 必须是非空路径列表")
        if self.parallelism < 1:
            problems.append("project.parallelism 必须 >= 1")
        if self.timeout_sec <= 0:
            problems.append("project.timeout_sec 必须 > 0")
        if self.quality_gate.min_mutation_score is not None and not (
            0 <= self.quality_gate.min_mutation_score <= 100
        ):
            problems.append("quality_gate.min_mutation_score 必须在 0-100 之间")
        if self.flaky.runs < 2:
            problems.append("flaky.runs 必须 >= 2（至少运行两次才能判断不稳定）")
        if self.mutation.exclude_operators:
            self.mutation.exclude_operators = normalize_operators(self.mutation.exclude_operators)
        # operators 在解析时已规范化
        if problems:
            raise ConfigError("配置校验失败:\n  - " + "\n  - ".join(problems))

    # -- 解析后的有效算子 -------------------------------------------------

    def effective_operators(self) -> list:
        ops = [o for o in self.mutation.operators if o not in self.mutation.exclude_operators]
        return ops

    # -- 目录 ------------------------------------------------------------

    def resolve_root(self) -> Path:
        return Path(self.project_root or (Path(self.config_path).parent if self.config_path else Path.cwd()))


# ---------------------------------------------------------------------------
# 加载
# ---------------------------------------------------------------------------


def _expect_dict(value, where: str) -> dict:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigError(f"{where} 应为映射（mapping），实际为 {type(value).__name__}")
    return value


def _take(raw: dict, proj: dict, key: str):
    """读取配置段：project 嵌套（PRD 示例风格）优先，顶层为兼容回退。"""
    if key in proj:
        return proj.pop(key)
    if key in raw:
        return raw.pop(key)
    return None


def _apply_env_overrides(cfg: ProjectConfig) -> None:
    """CI 环境变量覆盖（PRD FR-01：支持 CI 环境变量覆盖）。"""
    def _num(key, cast):
        v = os.environ.get(key)
        if v:
            try:
                return cast(v)
            except ValueError:
                raise ConfigError(f"环境变量 {key}={v!r} 无法解析为 {cast.__name__}")
        return None

    if os.environ.get("METATEST_TEST_CMD"):
        cfg.test_cmd = os.environ["METATEST_TEST_CMD"]
    if os.environ.get("METATEST_BUILD_CMD") is not None:
        cfg.build_cmd = os.environ["METATEST_BUILD_CMD"]
    p = _num("METATEST_PARALLELISM", int)
    if p:
        cfg.parallelism = p
    t = _num("METATEST_TIMEOUT_SEC", float)
    if t:
        cfg.timeout_sec = t
    if os.environ.get("METATEST_OUTPUT_DIR"):
        cfg.report.output_dir = os.environ["METATEST_OUTPUT_DIR"]
    if os.environ.get("METATEST_LANGUAGE"):
        cfg.language = os.environ["METATEST_LANGUAGE"]


def load_config(path, project_root=None) -> ProjectConfig:
    """从 YAML 文件加载配置。path 为空时使用当前目录的 metatest.yaml。"""
    path = Path(path) if path else Path.cwd() / CONFIG_FILE_NAME
    if not path.exists():
        raise ConfigError(f"配置文件不存在: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise ConfigError(f"配置文件 YAML 解析失败: {e}")
    if raw is None:
        raise ConfigError("配置文件为空")
    raw = _expect_dict(raw, "配置根节点")

    proj = _expect_dict(raw.pop("project", None), "project")
    mut = _expect_dict(_take(raw, proj, "mutation"), "project.mutation")
    # 允许把 operators 直接写在 mutation 外层（PRD 示例即如此）
    if "operators" in proj and "operators" not in mut:
        mut["operators"] = proj.pop("operators")
    gate = _expect_dict(_take(raw, proj, "quality_gate"), "project.quality_gate")
    flaky = _expect_dict(_take(raw, proj, "flaky"), "project.flaky")
    cache = _expect_dict(_take(raw, proj, "cache"), "project.cache")
    sandbox = _expect_dict(_take(raw, proj, "sandbox"), "project.sandbox")
    report = _expect_dict(_take(raw, proj, "report"), "project.report")
    adapter = _expect_dict(_take(raw, proj, "adapter"), "project.adapter")
    plugins = _expect_dict(raw.pop("plugins", None), "plugins")

    unknown_top = set(raw) - {"trust"}
    if unknown_top:
        # 宽松处理：顶层未知键警告式忽略
        pass

    try:
        mut_opts = MutationOptions(
            operators=normalize_operators(mut.get("operators"), strict=False),
            exclude_operators=normalize_operators(mut["exclude_operators"], strict=False) if mut.get("exclude_operators") else [],
            incremental=bool(mut.get("incremental", False)),
            exclude_globs=list(mut.get("exclude_globs") or []),
            include_globs=list(mut.get("include_globs") or []),
            fail_fast=bool(mut.get("fail_fast", False)),
            test_selection=bool(mut.get("test_selection", False)),
            strategy=str(mut.get("strategy", "auto")),
            rule_files=[str(p) for p in (mut.get("rule_files") or [])],
        )
        gate_opts = QualityGateOptions(
            enabled=bool(gate.get("enabled", True)),
            min_mutation_score=gate.get("min_mutation_score"),
            max_flaky=gate.get("max_flaky"),
            max_weak_assertions=gate.get("max_weak_assertions"),
            fail_on_survived=bool(gate.get("fail_on_survived", False)),
        )
        flaky_opts = FlakyOptions(runs=int(flaky.get("runs", 3)), enabled=bool(flaky.get("enabled", True)),
                                  isolate=bool(flaky.get("isolate", False)))
        cache_opts = CacheOptions(
            enabled=bool(cache.get("enabled", True)),
            dir=str(cache.get("dir", ".metatest")),
        )
        sandbox_opts = SandboxOptions(copy_exclude=list(sandbox.get("copy_exclude") or []))
        report_opts = ReportOptions(
            formats=list(report.get("formats") or ["html", "json", "junit_xml"]),
            output_dir=str(report.get("output_dir", ".metatest/report")),
        )
        cfg = ProjectConfig(
            name=str(proj.get("name", "unnamed")),
            language=str(proj.get("language", "python")),
            build_cmd=str(proj.get("build_cmd", "") or ""),
            test_cmd=str(proj.get("test_cmd", "") or ""),
            test_result_format=str(proj.get("test_result_format", "junit_xml")),
            source_roots=[str(r) for r in (proj.get("source_roots") or ["src"])],
            test_roots=[str(r) for r in (proj.get("test_roots") or ["tests"])],
            parallelism=int(proj.get("parallelism", 4)),
            timeout_sec=float(proj.get("timeout_sec", 120)),
            env={str(k): str(v) for k, v in _expect_dict(proj.pop("env", None), "project.env").items()},
            mutation=mut_opts,
            quality_gate=gate_opts,
            flaky=flaky_opts,
            cache=cache_opts,
            sandbox=sandbox_opts,
            report=report_opts,
            adapter=adapter,
            plugins=plugins,
            trust=bool(raw.get("trust", False)),
            junit_path=proj.get("junit_path"),
        )
    except (TypeError, ValueError, KeyError) as e:
        raise ConfigError(f"配置字段类型错误: {e}")

    _apply_env_overrides(cfg)
    cfg.config_path = str(path)
    cfg.project_root = str(Path(project_root) if project_root else path.parent)
    cfg.validate()
    if cfg.trust:
        # v0.1.1 起信任不再来自仓库内容（见 commands_allowed）；字段保留仅作兼容
        import logging

        logging.getLogger("metatest").debug(
            "配置中的 trust: true 已不再授予命令执行权（防止随仓库提交的恶意配置），"
            "请使用 metatest allow / --allow-commands / METATEST_ALLOW_COMMANDS"
        )
    return cfg


def trust_marker_path(project_root=None) -> Path:
    """用户级信任存储（仓库外，攻击者无法随仓库提交）。

    可用环境变量 METATEST_TRUST_STORE 覆盖存储位置（测试/多环境隔离用）。
    """
    override = os.environ.get("METATEST_TRUST_STORE")
    if override:
        return Path(override)
    return Path.home() / ".metatest" / "trusted.json"


def config_fingerprint(path) -> str:
    """配置内容哈希：信任绑定到具体内容，配置被篡改后自动失效。"""
    import hashlib

    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def grant_trust(config_path, project_root=None) -> dict:
    """把（绝对配置路径 → 内容指纹）写入用户级信任存储。metatest init / allow 调用。"""
    import json
    import time

    path = Path(config_path).resolve()
    store_path = trust_marker_path(project_root)
    store_path.parent.mkdir(parents=True, exist_ok=True)
    store = {}
    if store_path.exists():
        try:
            store = json.loads(store_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            store = {}
    entry = {
        "fingerprint": config_fingerprint(path),
        "granted_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    store[str(path)] = entry
    store_path.write_text(json.dumps(store, ensure_ascii=False, indent=1), encoding="utf-8")
    return entry


def revoke_trust(config_path, project_root=None) -> bool:
    import json

    path = Path(config_path).resolve()
    store_path = trust_marker_path(project_root)
    if not store_path.exists():
        return False
    store = json.loads(store_path.read_text(encoding="utf-8"))
    removed = store.pop(str(path), None) is not None
    store_path.write_text(json.dumps(store, ensure_ascii=False, indent=1), encoding="utf-8")
    return removed


def commands_allowed(cfg: ProjectConfig, explicit_allow: bool) -> bool:
    """安全边界（PRD 非功能-安全）：默认不执行不可信配置中的任意命令。

    可信判定（全部在仓库外完成，仓库内容无法自我授权）：
      1. metatest init / metatest allow 写入的用户级信任存储
         （键 = 配置绝对路径，值 = 配置内容指纹；配置被改动即失效）
      2. 命令行 --allow-commands（一次性放行）
      3. 环境变量 METATEST_ALLOW_COMMANDS=1（CI 中显式允许）

    注意：配置文件里写 trust: true **不再**授予执行权（v0.1.1 起弃用），
    否则攻击者可随仓库提交该字段诱导执行。
    """
    if explicit_allow:
        return True
    if os.environ.get("METATEST_ALLOW_COMMANDS", "").strip().lower() in ("1", "true", "yes", "on"):
        return True
    if not cfg.config_path:
        return False
    store_path = trust_marker_path(cfg.project_root)
    if not store_path.exists():
        return False
    import json

    try:
        store = json.loads(store_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    path = str(Path(cfg.config_path).resolve())
    entry = store.get(path)
    if not entry:
        return False
    return entry.get("fingerprint") == config_fingerprint(cfg.config_path)
