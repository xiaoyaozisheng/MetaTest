"""演示项目源码：包含边界、分支、异常处理、循环等多种结构。

刻意让测试覆盖不完整 —— 运行 metatest run 后报告中会展示"漏测变异"。
"""


def add(a, b):
    return a + b


def sub(a, b):
    return a - b


def mul(a, b):
    return a * b


def div(a, b):
    if b == 0:
        raise ZeroDivisionError("除数不能为 0")
    return a / b


def is_leap(year):
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def clamp(x, lo, hi):
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x


def sum_to(n):
    total = 0
    for i in range(n):
        total += i
    return total


def grade(score):
    if score >= 90:
        return "A"
    if score >= 60:
        return "B"
    return "C"


def safe_parse(text):
    try:
        return int(text)
    except ValueError:
        return None
