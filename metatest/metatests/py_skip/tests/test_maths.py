import pytest

from maths import add


def test_add():
    assert add(1, 2) == 3


@pytest.mark.skip(reason="功能未实现（元测试基准：验证跳过不会被误判为通过）")
def test_future_feature():
    assert add("a", "b") == "ab"
