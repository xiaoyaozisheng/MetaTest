"""模拟外部测试工具：存在失败检查，退出码 1。"""

import sys

CHECKS = [
    ("sum", 1 + 1 == 2),
    ("broken", 1 + 1 == 3),  # 已知答案：必失败
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
