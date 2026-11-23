from point import Point


def test_attributes():
    p = Point(1, 2)
    assert p.x == 1
    assert p.y == 2
    # 刻意不测 __repr__：其 return_value 变异将存活，
    # 但必须被启发式标记为"疑似等价"（dunder 方法内返回值变异）
