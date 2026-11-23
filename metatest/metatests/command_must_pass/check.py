"""模拟外部测试工具：全部检查通过，退出码 0。"""

import sys

CHECKS = [
    ("sum", 1 + 1 == 2),
    ("string", "a" + "b" == "ab"),
]


def main() -> int:
    failed = 0
    for name, ok in CHECKS:
        if ok:
            print(f"PASS {name}")
        else:
            print(f"FAIL {name}")
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
