# CI 集成

MetaTest 的退出码即为 CI 判定依据：
`0` 达标 · `1` 质量门禁失败 · `2` 平台/配置错误 · `3` 自检失败。

生成模板：`metatest ci github` / `metatest ci gitlab`。

## GitHub Actions

`.github/workflows/metatest.yml`（由 `metatest ci github --out` 生成）：

```yaml
name: metatest
on:
  pull_request:
  push:
    branches: [main]

jobs:
  selftest:
    # 元测试自检：平台自身不可信则整个 CI 失败（退出码 3）
    name: MetaTest selftest
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install metatest
      - run: metatest selftest

  mutation-gate:
    name: Mutation gate (incremental)
    runs-on: ubuntu-latest
    needs: selftest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }        # 增量变异需要完整历史
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install metatest pytest
      - name: Run mutation testing (PR 增量)
        env:
          METATEST_ALLOW_COMMANDS: "1"  # CI 显式允许执行配置中的命令
        run: |
          metatest run --incremental --diff-ref "origin/${{ github.base_ref }}" \
            --allow-commands
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: metatest-report
          path: .metatest/report/
```

要点：

- `needs: selftest` —— 先自检后评估；
- `fetch-depth: 0` —— 增量 diff 需要；
- `METATEST_ALLOW_COMMANDS=1` —— 安全边界：显式允许执行仓库配置中的命令；
- PR 场景用 `--diff-ref origin/<target>`，只评估改动相关变异体（中小项目 < 10 分钟）。

## GitLab CI

`.gitlab-ci.yml`（由 `metatest ci gitlab --out` 生成）：

```yaml
stages: [quality]

metatest-selftest:
  stage: quality
  image: python:3.12
  script:
    - pip install metatest
    - metatest selftest          # 退出码 3 时流水线失败

metatest-gate:
  stage: quality
  image: python:3.12
  variables:
    METATEST_ALLOW_COMMANDS: "1"
  script:
    - pip install metatest pytest
    - git fetch origin $CI_MERGE_REQUEST_TARGET_BRANCH_NAME || true
    - metatest run --incremental --diff-ref "origin/$CI_MERGE_REQUEST_TARGET_BRANCH_NAME" --allow-commands
  artifacts:
    when: always
    paths: [.metatest/report/]
```

## 门禁建议

```yaml
quality_gate:
  min_mutation_score: 80.0       # 主分支全量基线；PR 增量模式可单独调高
  max_flaky: 0                   # flaky 零容忍
  max_weak_assertions: 0
```

趋势管理：新代码变异得分不得低于既有基线，防止"测试质量退化"（PRD 1）。
报告产物（`report.html` / `results.json` / `mutation_junit.xml`）建议作为 CI artifact 保存；
`mutation_junit.xml` 可被 GitLab/GitHub 测试报告解析，漏测变异以失败用例形式展示。

## C 项目 CI

C 项目需在 CI 镜像中安装编译工具链（gcc/clang、可选 cmake）与 tree-sitter 依赖：

```yaml
- run: pip install "metatest[c]"
- run: apt-get install -y gcc cmake   # 如使用 ctest
```
