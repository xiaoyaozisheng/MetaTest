import pytest


@pytest.mark.skip(reason="元测试基准：全部用例被跳过")
def test_a():
    assert True


@pytest.mark.skip(reason="元测试基准：全部用例被跳过")
def test_b():
    assert True
