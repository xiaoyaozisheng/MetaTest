"""MetaTest 异常类型。"""

from __future__ import annotations


class MetaTestError(Exception):
    """平台错误基类。对应退出码 2。"""


class ConfigError(MetaTestError):
    """metatest.yaml 配置无效。"""


class AdapterError(MetaTestError):
    """适配器环境缺失或项目无法接入。"""


class SelfTestError(MetaTestError):
    """自检运行本身出错（区别于自检判定失败）。"""


class MutationError(MetaTestError):
    """变异生成/应用失败。"""
