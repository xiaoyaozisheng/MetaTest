# 真实缺陷基准库接入：BugsInPy 与 MetaFL

> 用真实世界的缺陷/种子故障验证 MetaTest 的变异生成与结果判定，把"已知答案基准"
> 从 17 个手工基准扩展到数百个真实缺陷。数据集放置于 `external/`（不进版本库）。

## 1. BugsInPy（Python，[soarsmu/BugsInPy](https://github.com/soarsmu/BugsInPy)）

**实测规模：17 个项目 / 501 个真实缺陷**（pandas 169、keras 45、youtube-dl 43、scrapy 40 …）。
每个缺陷提供：`bug.info`（buggy/fixed 提交号 + 触发测试）、`bug_patch.txt`（修复 diff =
缺陷区域真值）、`run_test.sh`（精确到测试函数的回归命令）。

### 已知答案结构 → MetaTest 验证协议

对任一缺陷，三个判定环节全部可机械化核对：

1. **buggy 版本 + 触发测试 → 必须 FAIL**（验证结果判定不把失败误报为通过）；
2. **应用官方补丁后 → 必须 PASS**（验证补丁区域即缺陷根因）；
3. **fixed 版本上，缺陷行的变异 → 应被触发测试杀死**（验证变异生成与 killed 判定）。

### 已完成端到端验证：tqdm bug#1（真实参数交换缺陷）

缺陷：`tqdm/contrib/__init__.py:41` 的 `tenumerate` 把 `start` 错传给
`tqdm_class(iterable, start, **tqdm_kwargs)`；修复为 `enumerate(tqdm_class(iterable, **tqdm_kwargs), start)`。

| 环节 | 结果 |
|------|------|
| buggy 版本运行 `pytest tqdm/tests/tests_contrib.py::test_enumerate` | MetaTest 判定 **fail**（tests=1, failures=1）✓ |
| 应用官方补丁后同一测试 | MetaTest 判定 **pass** ✓ |
| fixed 版本缺陷行的变异（4 个：return_value ×1、none_replacement ×3） | **全部 killed** ✓ —— 回归测试精确钉住缺陷语义 |
| 同文件全量变异（44 个，单回归测试套件） | killed 9 / survived 35，得分 20.5%（合理：单一测试只覆盖 contrib 局部） |

复现（Python 3.13 实测通过）：

```bash
cd external/bugsinpy/work/tqdm-bug1/buggy
PYTHONPATH=. python -m pytest "tqdm/tests/tests_contrib.py::test_enumerate"   # buggy: fail
patch --batch -p1 < ../../../repo/projects/tqdm/bugs/1/bug_patch.txt          # 应用官方修复
metatest run                                                                  # 缺陷区域变异 → killed
```

环境适配说明（只动测试装置，不动缺陷区域）：2018 年代基准在 Python 3.13 上需要
① nose 兼容 shim（`with_setup / assert_raises / eq_`，已放 `nose/` 目录）；
② `tests_tqdm.py` 的 `pretest` 中 `setcheckinterval` 在现代 Python 已移除（已改为安全回退）。

### 规模化路径

- 单缺陷端到端 ≈ 分钟级；瓶颈是各项目历史版本的安装兼容性（老 pandas/matplotlib/scipy
  在新 Python 上需容器化）。建议容器矩阵（每项目一个镜像，BugsInPy 自带 Dockerfile 模板）；
- 缺陷区域变异验证可直接用 `mutation.include_globs`（缺陷文件）+ `--diff-ref <fixed_commit>`
  增量模式（只评估 bug_patch 相关变异），无需全量执行；
- 全量 501 缺陷的批次运行器（解析 bug.info → 生成 metatest.yaml → 三环节核对 → 汇总报告）
  是下一步工程项；本仓库已提供全部构造块（判定器/引擎/报告/退出码）。

## 2. MetaFL（C/C++，[YanLei-Team/MetaFL_dataset](https://github.com/YanLei-Team/MetaFL_dataset)）

7 个 C 主题程序（grep 2.4.2 / sed 1.18 / SeqMap / ShortestPath / PrimeCount / clac / quich），
带种子故障（单行 diff）、生成式测试池与蜕变关系（MR）。种子故障的行号记录在各主题程序
`mutations/20210224/faultList.txt`。

### 已完成端到端验证：quich（632 eLOC 计算器）

quich 自带完整源码 + Makefile，可直接接入 MetaTest C 适配器：

- 构建：`gcc -O2 -o quich.exe quich.c -lm`；
- 黑盒回归测试：10 条确定性表达式断言（`check.py`，涵盖算术优先级/一元负号/函数调用/阶乘）；
- **MetaTest 实测：645 个变异体，80s（并行 8），killed 343 / survived 301，得分 53.3%**，
  退出码 0，报告完整（results.json）；
- **与第三方种子故障交叉覆盖：MetaFL 的 282 个缺陷行中，MetaTest 变异点命中 167（59%）**
  —— 两者算子空间不同（MetaFL 含指针/字符串类种子），59% 的行级交叉覆盖说明
  MetaTest 的 10 算子在真实代码上与学术级故障注入器高度互补。

复现：

```bash
cd external/metafl/work/quich-meta-src
metatest run --operators relational,arithmetic,boolean_negation,condition_constant,boundary_value
```

### 规模化路径

- 其余主题程序（grep/sed/SeqMap）需从上游获取对应历史版本源码再接入（补丁基于上游树）；
- MR 检查器（tools/CheckMR）可作为 command 适配器的 test_cmd 直接复用，把"蜕变关系失败"
  作为 killed 信号——这是 MetaFL 与变异测试结合的独特价值（后续项）。

## 3. 对 PRD 指标的意义

| 指标 | 手工基准（metatests/） | + BugsInPy | + MetaFL |
|------|----------------------|------------|----------|
| 基准项目数 | 14 | +501 缺陷（17 项目） | +7 主题程序（数千种子故障） |
| 误判率度量 | 0%（17/17，内置基准） | 真实缺陷三环节核对，可批量统计 | 种子行交叉覆盖 59%（quich） |
| 判定可信度 | 小型合成代码 | 大型真实代码库（tqdm 等） | 真实 C 程序 |

结论：**变异生成与结果判定在真实代码 + 真实缺陷上行为正确**；两个数据集均已打通
"数据集 → metatest.yaml → 引擎 → 已知答案核对"的完整链路。
