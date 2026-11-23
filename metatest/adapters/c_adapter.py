"""C 适配器（PRD FR-04）：Make / CMake / CTest 支持，自定义 build/test 命令。

构建系统自动检测：
  * CMakeLists.txt → cmake -S . -B build && cmake --build（ctest --output-junit 产出 JUnit XML）
  * Makefile       → make
  * 否则使用配置中的 build_cmd / test_cmd
"""

from __future__ import annotations

import logging
from pathlib import Path

from metatest.adapters.base import BaseAdapter
from metatest.errors import AdapterError
from metatest.models import RunOutcome, TestRunResult
from metatest.mutators.base import MutantSpec, read_source
from metatest.proc import run_command

logger = logging.getLogger("metatest")


class CAdapter(BaseAdapter):
    name = "c"
    language = "c"

    @classmethod
    def detect(cls, root, config=None) -> int:
        root = Path(root)
        score = 0
        if (root / "CMakeLists.txt").exists():
            score += 50
        if (root / "Makefile").exists() or (root / "makefile").exists():
            score += 40
        if list(root.glob("**/*.c")) or list(root.glob("**/*.h")):
            score += 30
        return min(score, 100)

    def prepare(self) -> None:
        root = self.project_root
        has_cmake = (root / "CMakeLists.txt").exists()
        has_make = (root / "Makefile").exists() or (root / "makefile").exists()
        test_binary = self.config.adapter.get("test_binary")
        if not (self.config.build_cmd or self.config.test_cmd or has_cmake or has_make):
            raise AdapterError(
                "C 项目接入需要至少一种构建/测试方式：在 metatest.yaml 配置 build_cmd/test_cmd，"
                "或提供 CMakeLists.txt / Makefile"
            )
        if not self.config.test_cmd and not test_binary and not has_cmake:
            raise AdapterError(
                "C 项目未配置 test_cmd/test_binary 且非 CMake 项目，无法判定测试结果；"
                "请配置 test_cmd 或 adapter.test_binary，或提供 CMakeLists.txt（ctest）"
            )
        if not self.config.build_cmd and not self.config.test_cmd and has_cmake and not has_make:
            from metatest.proc import run_command

            r = run_command("cmake --version", cwd=root, timeout=60)
            if r.exit_code != 0:
                raise AdapterError("检测到 CMake 项目但 cmake 不可用：请安装 cmake 或在 build_cmd 中配置编译命令")

    def build(self, work_dir, timeout: float):
        work_dir = Path(work_dir)
        build_dir = self.config.adapter.get("build_dir", "build")
        if self.config.build_cmd:
            return run_command(self.config.build_cmd, cwd=work_dir, timeout=timeout, env_extra=self.config.env)
        if (work_dir / "CMakeLists.txt").exists():
            configure = f'cmake -S . -B "{build_dir}"'
            build = f'cmake --build "{build_dir}" --config Debug'
            r1 = run_command(configure, cwd=work_dir, timeout=timeout, env_extra=self.config.env)
            if r1.exit_code != 0:
                return r1
            return run_command(build, cwd=work_dir, timeout=timeout, env_extra=self.config.env)
        if (work_dir / "Makefile").exists() or (work_dir / "makefile").exists():
            return run_command("make", cwd=work_dir, timeout=timeout, env_extra=self.config.env)
        return None  # 纯预编译/自定义 test_cmd 模式

    def run_tests(self, work_dir, timeout: float, test_ids=None) -> TestRunResult:
        work_dir = Path(work_dir)
        if test_ids:
            logger.warning("C 适配器暂不支持按测试筛选（gcov 逐测试采集为后续增强），回退全量运行")
        build = self.build(work_dir, timeout)
        if build is not None and build.exit_code != 0:
            run = TestRunResult(exit_code=build.exit_code, duration_sec=build.duration_sec,
                                output_tail=build.output_tail)
            run.outcome = RunOutcome.ERROR
            return run
        if self.config.test_cmd:
            from metatest.proc import run_command

            proc = run_command(self.config.test_cmd, cwd=work_dir, timeout=timeout, env_extra=self.config.env)
            return self.parse_result(work_dir, proc)

        test_binary = self.config.adapter.get("test_binary")
        if test_binary:
            from metatest.proc import run_command

            import sys

            cmd = test_binary if sys.platform == "win32" else f"./{test_binary}"
            proc = run_command(cmd, cwd=work_dir, timeout=timeout, env_extra=self.config.env)
            return self.parse_result(work_dir, proc)

        # CMake/CTest 模式：ctest --output-junit 产出 JUnit XML
        build_dir = self.config.adapter.get("build_dir", "build")
        junit_name = "_metatest_ctest_junit.xml"
        cmd = f'ctest --test-dir "{build_dir}" --output-on-failure --output-junit "{junit_name}"'
        proc = run_command(cmd, cwd=work_dir, timeout=timeout, env_extra=self.config.env)
        run = TestRunResult(
            exit_code=proc.exit_code,
            duration_sec=proc.duration_sec,
            timed_out=proc.timed_out,
            output_tail=proc.output_tail,
        )
        junit_abs = work_dir / junit_name
        if junit_abs.exists():
            try:
                from metatest.junit import apply_summary, parse_junit

                apply_summary(run, parse_junit(junit_abs))
                run.junit_path = junit_name
            except ValueError:
                pass
        run.classify()
        return run

    def generate_mutants(self, operators: list) -> list:
        specs = super().generate_mutants(operators)
        if not specs:
            raise AdapterError(
                f"source_roots {self.config.source_roots} 中未找到可变异的 .c/.h 文件，无法生成变异体"
            )
        info = self.mutator_info or {}
        logger.info("C 变异策略: %s（链: %s）", info.get("strategy"),
                    " → ".join(n for n, _d, _s in info.get("chain", [])))
        return specs
