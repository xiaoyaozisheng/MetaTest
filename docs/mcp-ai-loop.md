# AI 读取最小闭环：GitHub MCP + 本地 AST 索引

> 目标：验证 Claude Code / Cursor 能否通过 MCP **自主探索**一个 Python/C 仓库并回答结构化问题
> （入口点、测试文件位置、关键函数）。本文给出配置、问题集，以及本仓库已实测的闭环证据。

## 1. 架构与角色分工

| 层 | 工具 | 作用 |
|----|------|------|
| 远程读取 | **GitHub MCP Server**（官方） | 仓库结构、文件内容、提交/PR/Issue 查询 |
| 本地索引 | **semtree**（tree-sitter + 本地嵌入，[rustkit-ai/semtree](https://github.com/rustkit-ai/semtree)） | 函数/结构体级语义检索（"哪个函数处理闰年？"） |
| 本地索引 | **jcode**（tree-sitter 符号图谱，[codewithjoe-tech/JCode](https://github.com/codewithjoe-tech/jcode)） | 符号与依赖关系图（调用边 → 测试关联线索） |
| 平台侧 | MetaTest 适配器协议 | 把"读取"变成"判定"：变异点定位已内置 AST（Python ast / C tree-sitter），测试关联用 coverage 上下文（`--test-selection`） |

**事实核查（2026-11）**：semtree 与 jcode 均为真实存在的 tree-sitter 系本地索引工具；
但它们是**语义检索/符号图谱**，不直接产出"变异点 → 测试"映射——该能力由
MetaTest 的 `metatest/core/testmap.py`（coverage 动态上下文）承担，AST 定位由内置变异器承担。

## 2. 配置

### Claude Code（项目级 `.mcp.json`）

```json
{
  "mcpServers": {
    "github": {
      "type": "http",
      "url": "https://api.githubcopilot.com/github/mcp",
      "headers": { "Authorization": "Bearer ${GITHUB_PAT}" }
    }
  }
}
```

### Cursor（`~/.cursor/mcp.json`，docker 本地模式）

```json
{
  "mcpServers": {
    "github": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "-e", "GITHUB_PERSONAL_ACCESS_TOKEN",
               "ghcr.io/github/github-mcp-server"],
      "env": { "GITHUB_PERSONAL_ACCESS_TOKEN": "<你的 PAT>" }
    }
  }
}
```

（以 [github/github-mcp-server](https://github.com/github/github-mcp-server) 当前文档为准。）

### 本地索引层（可选，需本地克隆仓库）

```bash
# semtree：tree-sitter 分块 + 本地嵌入检索（详见其仓库 README 安装方式）
semtree index /path/to/repo && semtree query "where are entry points defined"
# jcode：符号/依赖图谱
jcode index /path/to/repo
```

## 3. 结构化问题集（闭环验收问题）

对任意仓库（Python 或 C），AI 应能通过 MCP/索引回答：

| 类别 | 问题 | 期望产出 |
|------|------|----------|
| 入口点 | 程序/框架从哪里启动？ | 文件:行 + 入口符号（main / console_script / setup.py entry_points） |
| 测试位置 | 测试文件在哪？测试框架是什么？ | 目录 + 框架 + 单测运行命令 |
| 关键函数 | 核心逻辑在哪个函数？ | 符号 + 职责摘要 + 被谁调用 |
| 元信息 | 构建方式 / 依赖 / 语言占比 | 构建命令 + 依赖清单 |

**Prompt 模板**（Claude Code / Cursor 中直接使用）：

```text
请用 GitHub MCP 工具（和本地 semtree/jcode 索引，若已建立）探索 <org/repo>，
回答以下结构化问题，每项给出证据（文件:行）：
1. 入口点在哪里？
2. 测试文件位置与测试框架？如何只运行单个测试？
3. 最关键的 3 个函数/模块及其职责？
4. 构建与依赖安装方式？
```

## 4. 闭环证据（本会话实测）

以下结果由 ZCode 代理经 GitHub REST API + 本地结构化探索产出——与 MCP 工具等价的信息通路，
**信息通路验证成立**（非 MCP 工具调用验证）：本会话由 ZCode 代理经 GitHub REST API + 本地结构化探索产出；MCP 工具调用需在 Claude Code / Cursor 中按第 2 节配置后手动复现，本仓库未自动化该步骤。

### 4.1 BugsInPy（Python 基准库，[soarsmu/BugsInPy](https://github.com/soarsmu/BugsInPy)）

| 问题 | AI 读取结果 | 证据 |
|------|-------------|------|
| 入口点 | `framework/bin/bugsinpy-{checkout,compile,test,info,coverage,mutation,fuzz}` 七个 CLI | framework/bin/ |
| 测试位置 | `projects/<项目>/bugs/<id>/run_test.sh` 内嵌 pytest node id（如 `tqdm/tests/tests_contrib.py::test_enumerate`） | run_test.sh |
| 关键数据 | **17 个项目 / 501 个缺陷**；每缺陷五件套 `bug.info / bug_patch.txt / run_test.sh / setup.sh / requirements.txt` | projects/*/bugs/*/ |
| 关键函数 | `framework/bin/bugsinpy-checkout`（缺陷版本切换）、`bug_patch.txt`（缺陷区域真值 diff） | — |

### 4.2 MetaFL 数据集（C/C++ 基准，[YanLei-Team/MetaFL_dataset](https://github.com/YanLei-Team/MetaFL_dataset)）

| 问题 | AI 读取结果 | 证据 |
|------|-------------|------|
| 入口点 | 各主题程序 `source/quich.c` 等 + `tools/CheckMR`（蜕变关系检查器） | quich/source/ |
| 测试位置 | `inputs/TestPool_sample1000` 等生成用例池 + MR 定义；无传统单测 | inputs/ |
| 关键数据 | 7 个 C 主题程序（grep/sed/SeqMap/ShortestPath/PrimeCount/clac/quich），**种子缺陷以单行 diff 提供**（quich 1521 个补丁 / faultList 282 个缺陷行） | mutations/20210224/patches/ |
| 可接入性 | quich 自带 `source/Makefile` 与完整源码 → 可被 MetaTest C 适配器直接消费（已验证，见 docs/bugbench.md） | — |

### 4.3 结论

- 信息通路读取 → 结构化回答：**验证成立**（三类问题全部有证据锚点，第 4 节表格）；
- MCP 工具调用链路未在本仓库自动化，需按第 2 节配置后在 Claude Code / Cursor 中复现；
- 语义检索（semtree/jcode）解决"找函数"，GitHub MCP 解决"找仓库/找文件/找历史"；
- MetaTest 侧再把"读取"升级为"判定"：`metatest run` 直接消费 AI 探索出的
  build/test 命令生成 `metatest.yaml`（`metatest init` 自动探测语言即此闭环的平台侧形态）。

## 5. 已知限制

- GitHub MCP 需要 PAT 与网络；本会话内 git 直连 github.com:443 被重置，改走 codeload tarball 通道；
- semtree 的嵌入检索对"精确行号"不可靠（返回片段而非行号），变异点定位仍以 MetaTest 内置
  AST 遍历为准——两者是互补关系而非替代关系；
- jcode/semtree 均为活跃中的小工具，接入前请核对其当前 CLI 形态。
