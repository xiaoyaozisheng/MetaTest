"""交替通过/失败的"flaky"测试（元测试基准）。

第 1、3、5…次运行通过；第 2、4…次运行失败。
运行计数写入 FLAKY_STATE_FILE（绝对路径，见 metatest.yaml env）。
"""

import os
from pathlib import Path


def _state_path() -> Path:
    return Path(os.environ.get("FLAKY_STATE_FILE", ".flaky_state"))


def test_flaky():
    state = _state_path()
    count = int(state.read_text(encoding="utf-8")) if state.exists() else 0
    state.write_text(str(count + 1), encoding="utf-8")
    if count % 2 == 1:
        raise AssertionError("偶发失败（元测试基准：模拟 flaky）")
