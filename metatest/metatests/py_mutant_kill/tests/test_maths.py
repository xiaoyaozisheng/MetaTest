import pytest

from maths import add, clamp, is_leap, safe_div


def test_add():
    assert add(2, 3) == 5
    assert add(-1, 1) == 0


def test_leap():
    assert is_leap(2024) is True
    assert is_leap(2000) is True
    assert is_leap(1900) is False
    assert is_leap(2023) is False


def test_clamp():
    assert clamp(5, 1, 10) == 5
    assert clamp(0, 1, 10) == 1
    assert clamp(11, 1, 10) == 10


def test_safe_div():
    assert safe_div(6, 3) == 2
    # match 约束可区分"显式校验"与"自然除零错误"：raise 被删除时自然除零
    # 的消息是 "division by zero"，不匹配 "除零"，变异被杀死
    with pytest.raises(ZeroDivisionError, match="除零"):
        safe_div(1, 0)
