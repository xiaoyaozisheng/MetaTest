"""官方 CI 模板（PRD FR-09/P1：GitHub Actions / GitLab CI）。"""

GITHUB_ACTIONS = """\
# MetaTest CI 示例（GitHub Actions）
# 保存为 .github/workflows/metatest.yml
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
        with:
          python-version: "3.12"
      - run: pip install metatest
      - run: metatest selftest
  mutation-gate:
    name: Mutation gate (incremental)
    runs-on: ubuntu-latest
    needs: selftest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0            # 增量变异需要完整历史以 diff
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install metatest pytest
      - name: Run mutation testing (PR 增量)
        env:
          METATEST_ALLOW_COMMANDS: "1"   # CI 显式允许执行配置中的命令
        run: |
          metatest run --incremental --diff-ref "origin/${{ github.base_ref }}" \\
            --allow-commands
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: metatest-report
          path: .metatest/report/
"""

GITLAB_CI = """\
# MetaTest CI 示例（GitLab CI）
# 保存为 .gitlab-ci.yml
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
    # 增量门禁：与目标分支 diff
    - git fetch origin $CI_MERGE_REQUEST_TARGET_BRANCH_NAME || true
    - >
      metatest run --incremental
      --diff-ref "origin/$CI_MERGE_REQUEST_TARGET_BRANCH_NAME"
      --allow-commands || gate=$?; if [ "${gate:-0}" -ge 2 ]; then exit $gate; fi
    # 退出码 1 = 质量门禁失败：按需阻断
    - if [ "${gate:-0}" -eq 1 ]; then echo "Mutation score below gate" && exit 1; fi
  artifacts:
    when: always
    paths: [.metatest/report/]
"""


def template_for(ci: str) -> str:
    if ci == "github":
        return GITHUB_ACTIONS
    if ci == "gitlab":
        return GITLAB_CI
    raise ValueError(f"未知 CI: {ci}（支持 github/gitlab）")
