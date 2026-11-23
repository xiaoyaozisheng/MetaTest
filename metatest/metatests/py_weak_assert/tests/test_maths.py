from maths import add, clamp


def test_no_assertion():
    # 弱断言类型 1：只执行代码，没有任何断言 —— 测试"看起来在测"，实际什么也没验证
    add(2, 3)


def test_trivial_assert():
    # 弱断言类型 2：断言恒真常量
    assert True


def test_same_compare():
    # 弱断言类型 3：自比较断言（x == x 恒真）
    x = 5
    assert x == x


def test_strong():
    # 对照组：强断言，不应被标记
    assert add(2, 3) == 5
    assert clamp(0, 1, 10) == 1
