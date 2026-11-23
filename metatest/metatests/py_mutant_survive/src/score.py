def grade(score):
    if score >= 90:
        return "A"
    if score >= 60:
        return "B"
    return "C"


def unused_branch(x):
    # 元测试基准：该函数没有任何测试覆盖
    if x < 0:
        return "negative"
    return "non-negative"
