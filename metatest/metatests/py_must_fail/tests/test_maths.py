from maths import add


def test_broken_expectation():
    # 已知答案：该测试必失败（基准项目，用于验证平台不会把失败误报为通过）
    assert add(2, 3) == 6
