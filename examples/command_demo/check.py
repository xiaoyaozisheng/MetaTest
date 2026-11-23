"""模拟外部测试工具：演示"任意语言命令级接入"。

真实场景中这里可以是任何语言的测试命令（shell 脚本、Go 二进制、
JUnit 运行器……），只要退出码 0=通过、非 0=失败即可接入 MetaTest。
"""

import sys

CHECKS = [
    ("checksum", 1 + 1 == 2),
    ("concat", "foo" + "bar" == "foobar"),
]


def main() -> int:
    failed = 0
    for name, ok in CHECKS:
        print(("PASS " if ok else "FAIL ") + name)
        failed += 0 if ok else 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
