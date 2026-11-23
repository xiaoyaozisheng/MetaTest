def add(a, b):
    return a + b


def is_leap(year):
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def clamp(x, lo, hi):
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x


def safe_div(a, b):
    if b == 0:
        raise ZeroDivisionError("除零")
    return a / b
