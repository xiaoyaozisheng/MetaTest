"""MetaTest — 测试有效性评估与元测试平台。

回答三个更上层的问题：
1. 现有测试套件是否有效？（变异测试）
2. 测试套件质量是否在退化？（flaky / 弱断言 / 重复测试 / 覆盖率结合）
3. 测试工具本身是否可信？（元测试自检 metatest selftest）
"""

__version__ = "0.1.0"

from metatest.exitcodes import EXIT_GATE, EXIT_OK, EXIT_PLATFORM, EXIT_SELFTEST

__all__ = ["__version__", "EXIT_OK", "EXIT_GATE", "EXIT_PLATFORM", "EXIT_SELFTEST"]
