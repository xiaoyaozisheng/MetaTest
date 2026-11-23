from maths import slow_computation


def test_hangs():
    # 已知答案：睡眠远超 timeout_sec=2，用于验证超时判定与进程终止
    assert slow_computation(30)
