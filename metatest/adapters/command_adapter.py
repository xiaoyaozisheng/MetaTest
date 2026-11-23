"""Command 适配器（PRD FR-02/FR-03）：任意项目命令级接入。

只需提供 build_cmd/test_cmd 与结果格式（exit_code 或 junit_xml）即可接入
flaky 检测、测试结果校验和报告；不提供变异（零变异体）。
"""

from __future__ import annotations

from pathlib import Path

from metatest.adapters.base import BaseAdapter


class CommandAdapter(BaseAdapter):
    name = "command"
    language = "command"

    @classmethod
    def detect(cls, root, config=None) -> int:
        if config is not None and config.language == "command":
            return 100
        return 0

    def prepare(self) -> None:
        if not self.config.test_cmd:
            from metatest.errors import AdapterError

            raise AdapterError("command 适配器要求配置 test_cmd")

    # generate_mutants：继承 base 统一实现 —— 配置 mutation.rule_files 时
    # 任意语言项目也能做规则化变异（universalmutator 思路）；未配置规则时零变异体。
