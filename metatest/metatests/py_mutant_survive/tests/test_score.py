from score import grade


def test_grade():
    assert grade(95) == "A"
    assert grade(75) == "B"
    assert grade(30) == "C"
    # 刻意不测试 unused_branch —— 元测试基准：验证平台能报告漏测变异
