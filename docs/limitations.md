# 限制说明与边界（PRD 非目标 + 已知限制）

## 产品边界（PRD 2.3 非目标）

- **不替代项目原有测试框架** —— MetaTest 只评估测试，不接管测试。
- **不承诺零配置覆盖"所有项目"** —— "所有项目"指通过命令级适配器协议接入；深度语法级
  变异仅覆盖 Python 与 C。
- **MVP 不做 SaaS 托管** —— 本地运行，不上传源码与结果到任何外部服务。
- **Java/JS/Go 无深度语法级变异** —— 仅命令级接入（flaky 检测、结果校验、报告）。
- **不做测试管理平台** —— 无用例管理/需求管理/手工测试管理。

## 能力边界（预期管理）

* **不包含 AI 语义理解**：MetaTest 的仓库探索/布局推断是确定性规则（`metatest init` 的
  目录启发式），不使用 LLM/MCP；"AI 自主探索 + 等价变异 LLM 判定"属于 PRD P2 路线，
  当前外置方案见 docs/mcp-ai-loop.md。等价变异判定仅为启发式（dunder 方法提示）
  + 人工标记（equivalents.yaml），不要预期平台自动识别全部等价变异。
* **C 变异引擎分级**：tree-sitter（AST 级，推荐）与词法级回退在报告中分引擎统计
  （`engine` 字段 / `engine_scores`）；`c_parser: auto` 在缺依赖时回退并显著告警，
  要求严格保证时在配置显式写 `c_parser: tree_sitter`（缺依赖退出码 2）。

## 已知限制

### 变异测试

- **等价变异体**：无法完全自动识别。缓解：报告"疑似等价"启发式提示 + `.metatest/equivalents.yaml`
  人工标记（标记后不计入分母）。边界值的对称变异（如 `x < lo` → `x <= lo` 在闭区间函数中）
  常为等价变异，属于正常现象。
- **运行成本**：每个变异体需要完整构建+测试（N 个变异 ≈ N 次测试套件运行）。缓解：增量模式、
  并行、缓存、超时与 fail_fast。大型项目建议 PR 增量门禁 + 主干定期全量基线。
- **沙箱按目录复制**：每个变异体复制整个项目（排除 .git/构建产物）。超大仓库（>1GB）复制
  开销显著；PRD P1 的 C 高性能执行器/容器沙箱为后续增强。
- **超时变异**：while→False / 死循环类变异消耗完整超时窗口；timeout 单独统计不计入得分分母。

### 跳过与可信度

- 部分跳过（pass_with_skips）不阻断评估但在报告/建议中提示；全部跳过直接拒绝评估
  （基线 all_skipped → 退出码 2；变异运行 all_skipped → error 状态）。

### 语言支持

- **Python**：基于 AST，语义变异覆盖 PRD 附录 10 个算子；不支持 `is/is not`、`in/not in`
  关系替换与 lambda 体变异（控制变异体噪声）。
- **C**：tree-sitter 后端 AST 级；无依赖回退为词法级保守方案（`*`/`/` 算术替换、语句删除、
  实参 NULL 替换在回退模式下不生成）。C 无异常机制，`exception_removal` 不适用。
  编译失败的变异计为 error（不计入得分），如需计为 killed 请自行调整算子白名单。
- **command 接入**：无语法级变异；结果粒度取决于接入方是否产出 JUnit XML（退出码模式下
  无用例级明细，flaky 检测退化为整体判定）。
- **unittest 直跑**（`python -m unittest`）无原生 JUnit 输出：按退出码判定（无用例明细）；
  推荐用 pytest 运行 unittest 套件（pytest 完全兼容）。

### 平台

- 兼容 Python 3.10+；Linux/macOS 优先，Windows 已验证可运行（CI 模板以 Linux 为基准）。
- Windows 下 `test_cmd` 经 cmd.exe 执行：命令写法需兼容 cmd（示例已验证）。
- flaky 检测依赖测试的确定性外部状态（如文件计数）在沙箱间共享 —— 使用 `FLAKY_STATE_FILE`
  约定；基于随机/时间的 flaky 开箱即用。
- 缓存键包含测试命令与超时：修改这两者会使既有缓存失效（代码未变也不会复用）。
- 覆盖率×变异得分结合需要项目提供 cobertura 格式 `coverage.xml`（如 pytest-cov 产出）。
- **测试关联筛选（test_selection）**：仅支持 Python/pytest；fixture setup/teardown 行不计入
  映射；结果与全量一致的前提是测试确定性与无跨测试耦合。C 侧等价能力（gcov 逐测试采集）
  未内置，`--test-selection` 在 C 项目上回退全量运行并告警。coverage.py 的查询缓存要求
  每上下文新建 CoverageData 实例（已在 testmap.py 处理）。

### 真实缺陷基准库（BugsInPy / MetaFL）

- 数据集位于 `external/`（不入版本库）；老版本项目在新型 Python 上需要环境适配
  （如 tqdm 2018 版需 nose 兼容 shim），适配只允许动测试装置、不动缺陷区域；
- BugsInPy 批量化运行需要各项目历史版本的容器化安装（自带 Dockerfile 模板）；
  MetaFL 的 grep/sed/SeqMap 需要从上游获取对应历史源码（数据集仅 quich 自带完整源码）。

## 开放问题（PRD 第 10 节，当前取舍）

| 开放问题 | 当前取舍 |
|----------|----------|
| C 变异引擎 Clang AST 还是 tree-sitter？ | tree-sitter（可移植优先），`adapter.c_parser` 可切换；词法回退分引擎统计、可显式禁用 |
| C 高性能执行器独立二进制插件？ | 未实现（P1/P2 预留插件接口） |
| 等价变异是否引入 LLM 辅助判定？ | 未实现（P2）；当前为启发式 + 人工标记 |
| 报告本地 Web 服务还是纯静态 HTML？ | 纯静态自包含 HTML（无依赖，artifact 友好） |
| 容器沙箱是否作为 MVP 可选项？ | 未实现；MVP 为目录级沙箱 + 进程级隔离与超时 |
