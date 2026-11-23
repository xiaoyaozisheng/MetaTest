"""演示测试套件：覆盖了主流程，但存在明显漏测点。

变异测试会暴露这些缺口（对比覆盖率的差异）。
"""

import pytest

from calc import add, clamp, div, grade, is_leap, sub


def test_add():
    assert add(2, 3) == 5
    assert add(-1, 1) == 0


def test_sub():
    assert sub(5, 3) == 2


def test_div():
    assert div(6, 3) == 2
    with pytest.raises(ZeroDivisionError, match="除数"):
        div(1, 0)


def test_is_leap():
    assert is_leap(2024) is True
    assert is_leap(2000) is True
    assert is_leap(2023) is False
    # 漏测点：没有测 1900（世纪非闰年）→ 相关变异会存活


def test_clamp():
    assert clamp(5, 1, 10) == 5
    # 漏测点：没有测下/上边界 → 边界变异会存活
    # assert clamp(0, 1, 10) == 1
    # assert clamp(11, 1, 10) == 10


def test_grade():
    assert grade(95) == "A"
    assert grade(75) == "B"
    assert grade(30) == "C"
    # 漏测点：没有测 90/60 边界值


def test_no_assertion_yet():
    # 弱断言示例：只调用不断言（质量分析会标记）
    add(1, 2)
