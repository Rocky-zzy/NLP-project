# B 部分实施计划：Conformal Factuality 长回答线

## Overview

B 负责复现 conformal factuality，并在固定的 FActScore 子集上完成双目标水平、校准集大小网格、失败案例分析和报告 1b/2b/3b 三节。主线只读取上游已缓存的 claim、人工标注和 `frequency-score`，不需要 GPU 或 API；目标是在 2026-11-23 前交付可复现代码、6 个正式结果 JSON、图表、案例分析和报告草稿。

上游数据实际为 50 个 prompt、408 条 claim。固定切分是 25 条 test、5 条 dev、20 条 calibration pool。`data/factscore_annotations.jsonl` 和 `out/factscore_subclaims_with_scores.jsonl` 虽然以 `.jsonl` 结尾，实际都是单个 JSON 对象 `{"data": [...]}`，需要专用 loader，不能直接使用现有的逐行 JSONL reader。

## Architecture Decisions

- 只移植上游必要算法：rank score、conformal quantile、claim filtering，不在 B 目录重写 claim 拆分或打分。
- 课程要求的是“保留 claim 全部正确”，因此主实验固定 claim-level 正确比例为 \(a=1\)。\(\alpha=0.1/0.2\) 只描述 conformal 错误率目标 \(1-\alpha=0.9/0.8\)。
- 上游 `factscore.py` 中 `ALPHA = 0.2` 与 `REQUIRED_FRAC_CORRECT = 0.96` 是两个不同参数；不能把后者解释成 \(1-\alpha\)。B 手册中的相关表述需要在实现时修正。
- 阈值只在 calibration subset 上拟合，之后一次性应用到冻结的 test set；test 不参与阈值、参数或案例选择。
- 主方法固定 `confidence_method = frequency`，但按照上游定义排序时使用 `frequency-score + noise`，保留 `>= threshold` 的 claim。
- 团队确认校准集大小为 calibration pool 的 `{0.5, 0.75, 1.0}`，即 10 / 15 / 20 条回答。
- 正确 claim 的标注集合沿用上游 `{"Y", "S"}`；`"N"` 和 `"U"` 都视为不正确。
- “空响应”定义为过滤后没有保留任何 claim，而不是必须等到生成文本等于空字符串。`Abstain.` 如果对应 0 条保留 claim，也计入 empty。
- 所有正式数字由 `confqa.common.results.run_result(..., pipeline="fact")` 写入 `exp/results/`；工作区 dirty 时生成的 JSON 只能调试，不能进入报告。
- B 不修改 C 拥有的 `src/confqa/common/`。若共享图需要新增误差棒字段，先与 C 对齐，或由 C 更新公共绘图接口。

## Task List

### Phase 1: Data and reproducible core

## Task 1: 固定上游输入与复现基线

**Description:** 克隆并检出 `conformal-factual-lm` 的固定 commit，核对 FActScore 输入、标注统计、固定 split 和上游缓存是否一致。记录不能由 git 跟踪恢复的输入哈希与已知限制。

**Acceptance criteria:**

- 上游仓库固定在 `6022b4c90c6580f524f123b0cb97bbb61ab621d1`，并记录 annotation、scored claims 和 survey 文件的 SHA-256。
- 核对 50 个 prompt、408 条 claim；标注分布为 `Y=235`、`S=52`、`N=75`、`U=46`，固定 split 恰好覆盖全部 50 个 position ID 且无交集。
- 记录 `factscore_annotations` 不含原始回答、仅 survey 文件保留最后 30 个 prompt 的原始/过滤回答这一数据限制。

**Verification:**

- `git -C third_party/conformal-factual-lm rev-parse HEAD`
- `shasum -a 256` 校验上述三个输入文件
- `jq` 汇总 records、claims、annotation、split 数量并与预期逐项比较

**Dependencies:** None

**Files likely touched:**

- `docs/reference/factscore-inputs.md`

**Estimated scope:** Small

## Task 2: 实现 FActScore loader 与 split 对齐

**Description:** 在 B 包中读取上游的 wrapped JSON、FActScore position ID 和固定 split，转换成内部统一的 response/claim 记录，确保 test 与 calibration 严格隔离。

**Acceptance criteria:**

- loader 支持当前 `{"data": [...]}` 格式，并按 `factscore-%04d` 生成稳定 ID。
- 输出每条记录包含 `pid`、`prompt`、`claims`；每条 claim 保留文本、annotation、frequency score 和 noise。
- 重复 ID、split 中缺失 ID、split 间重叠或 claim 分数缺失时立即报错。

**Verification:**

- `pytest tests/test_factuality_data.py`
- 手工加载 1 条记录，核对 prompt、claim 数量、annotation 和 `frequency-score`

**Dependencies:** Task 1

**Files likely touched:**

- `src/confqa/factuality/data.py`
- `tests/test_factuality_data.py`

**Estimated scope:** Small

## Task 3: 移植 conformal factuality 核心算法

**Description:** 实现并测试上游 `get_r_score`、`compute_threshold` 与 filtering 的最小等价版本。主实验使用 \(a=1\)、`frequency-score + noise` 和有限样本 conformal quantile。

**Acceptance criteria:**

- 给定 calibration records，阈值严格按 \(q=\lceil(n+1)(1-\alpha)\rceil\) 对应的升序 r-score 计算。
- `Y` 和 `S` 为正确，`N`、`U` 为错误；`a=1` 时 rank score 反映“保留前缀何时第一次出现错误 claim”。
- 简单固定 fixture 的阈值和上游函数一致，边界条件 `>= threshold`、空 claim、空 calibration 都有测试。

**Verification:**

- `pytest tests/test_factuality_conformal.py`
- 用上游函数在相同 fixture 与参数下运行一次交叉核对，不调用 API

**Dependencies:** Task 2

**Files likely touched:**

- `src/confqa/factuality/conformal.py`
- `tests/test_factuality_conformal.py`

**Estimated scope:** Medium

### Checkpoint: Data and core

- [x] 上游输入统计和哈希均可追溯
- [x] loader、split 对齐和核心算法测试通过
- [x] 人工抽查至少 2 条记录与 1 个阈值计算

### Phase 2: Baseline and controlled grid

## Task 4: 生成双 \(\alpha\) 基线结果

**Description:** 用冻结 test set 和 `calib_frac=0.5` 跑 `alpha=0.1/0.2` 两条基线，计算课程要求的 all-correct、retention 和 empty rate，并写入带 provenance 的结果 JSON。

**Acceptance criteria:**

- 产出 `exp/results/fact__a0.1__calib0.5.json` 与 `fact__a0.2__calib0.5.json`，每个结果包含 split hash、calibration/test 数量、threshold、`n_responses=25` 和三个主指标。
- `all_correct_nonempty`、`retention`、`empty_rate` 均有固定 seed 的 response-level bootstrap 95% CI；retention 的 CI 通过重采样 response 后重新按总 claim 数计算。
- 正式结果在干净 checkout 中重跑后 `reportable=true`，若指标趋势与“更严格目标通常保留更少 claim”不符，必须写入结果说明并复核，不静默改数。

**Verification:**

- `pytest tests/test_factuality_evaluate.py`
- `python -m confqa.factuality.cli baseline --config configs/factuality.yaml`
- `jq` 检查两个 JSON 的字段、split hash 和 `reportable`

**Dependencies:** Task 3

**Files likely touched:**

- `configs/factuality.yaml`
- `src/confqa/factuality/evaluate.py`
- `src/confqa/factuality/cli.py`
- `tests/test_factuality_evaluate.py`

**Estimated scope:** Medium

## Task 5: 生成 \(\alpha \times\) 校准集大小网格

**Description:** 保持 test、dev、seed 和 confidence method 不变，只改变 calibration pool 的抽样比例，形成 2 个目标水平 × 3 个校准比例的 6 个正式结果。

**Acceptance criteria:**

- 产出 6 个命名符合 schema 的结果 JSON；相同 `alpha/calib_frac` 重跑得到相同 calibration IDs、threshold 和指标。
- 三个 calibration subset 均由固定 seed 从同一 20 条 pool 中无放回抽取，test 始终是同一 25 条。
- 汇总表记录每个点的 threshold、三项指标、CI 和来源文件名；趋势违反预期时保留结果并解释，不调参筛选。

**Verification:**

- `python -m confqa.factuality.cli grid --config configs/factuality.yaml`
- `pytest`
- `python -m confqa.factuality.cli validate-results`

**Dependencies:** Task 4

**Files likely touched:**

- `src/confqa/factuality/evaluate.py`
- `src/confqa/factuality/cli.py`
- `tests/test_factuality_evaluate.py`
- `docs/reference/schemas.md`（仅当新增结果字段，且先告知 C）

**Estimated scope:** Medium

### Checkpoint: Baseline and grid

- [x] 6 个结果 JSON 都是 `reportable=true`
- [x] 每个数字能指回一个 result 文件和 split hash
- [x] 小样本阈值、CI 和趋势异常已记录

### Phase 3: Failure analysis and report

## Task 6: 完成空响应、过度删减与排除偏差分析

**Description:** 从正式结果与上游 cached survey 中挑选成功/失败案例，分析过滤后 factuality 变高但内容不足以回答问题的现象，并审计 claim 提取、merge 和样本排除。

**Acceptance criteria:**

- 交付至少 2 个“过滤后仍不足以回答问题”和 2 个“过滤保留主要正确信息”的案例；每条包含原始回答（或明确标注来源缺失）、保留 claims、删除 claims 和是否能回答 prompt 的判断。
- empty rate 与正式 result JSON 一致，并单列 `0` 条保留 claim 的样本；不把空集合因“vacuous all-correct”误算成有信息响应。
- 报告 50 条记录的 empty claim set、缺少 accepted claims、缺少 merged output 或解析失败数量；无法从缓存恢复的失败率必须标为未知，不得猜测。

**Verification:**

- `pytest tests/test_factuality_cases.py`
- `python -m confqa.factuality.cli cases --config configs/factuality.yaml`
- 人工逐条核对至少 4 个案例的 prompt、claims 和保留/删除判断

**Dependencies:** Task 4

**Files likely touched:**

- `src/confqa/factuality/cases.py`
- `tests/test_factuality_cases.py`
- `docs/analysis/B-factuality-cases.md`

**Estimated scope:** Medium

## Task 7: 生成报告可用图表与主表

**Description:** 从 6 个 result JSON 生成 retention–factuality 主图和 α × calibration × 三指标汇总表，供 A/C 做短长回答对比。

**Acceptance criteria:**

- `figures/retention_vs_factuality.png` 同时展示两个目标水平和三个 calibration 点，并带 95% CI 或明确说明当前小样本下未支持误差棒。
- 汇总表中的每项都带有 result 文件名、threshold、sample size 和 CI，A 可不询问 B 直接引用。
- 图与表只从 `exp/results/*.json` 生成，不手工抄数字；若修改公共绘图代码，必须先取得 C 同意。

**Verification:**

- `pytest tests/test_factuality_report.py`
- `python -m confqa.factuality.cli report --config configs/factuality.yaml`
- 打开生成图检查标签、图例、坐标范围与 6 个点

**Dependencies:** Task 5

**Files likely touched:**

- `src/confqa/factuality/report.py`
- `tests/test_factuality_report.py`
- `figures/retention_vs_factuality.png`

**Estimated scope:** Medium

## Task 8: 写报告 1b/2b/3b 并完成交接

**Description:** 将方法、基线、失败分析和网格结果写成英文报告草稿，并整理 H3/H5/H7 所需的可运行入口、结果 JSON 与案例证据。

**Acceptance criteria:**

- 1b 清楚说明输入、输出、calibration procedure 和 correctness criterion；2b 覆盖成功/失败案例、空响应和难例排除；3b 覆盖双目标水平、校准网格和趋势解释。
- 每个数字标注对应 `exp/results/*.json`，每张图标注生成命令；明确说明 25 条 test 是小规模复现，不宣称论文级 factuality guarantee。
- H3/H5/H7 各有可执行入口、输入输出示例和验收命令；C 能在不询问 B 的情况下跑出同格式结果。

**Verification:**

- 按 `docs/reference/repro_checklist.md` 从干净环境重跑 B 主线
- `pytest` 与 `ruff check .` 通过
- C 独立执行 H3 入口并得到相同格式结果

**Dependencies:** Task 6, Task 7

**Files likely touched:**

- `reports/B-factuality-sections.md`
- `src/confqa/factuality/README.md`
- `docs/manuals/B-factuality.md`

**Estimated scope:** Medium

### Checkpoint: Complete

- [ ] 3 个主指标、6 个网格结果、主图和 4+ 案例均存在
- [ ] 报告 1b/2b/3b 每个数字可追溯
- [ ] H3/H5/H7 可由 C 独立复现
- [ ] 总结已验证限制和负结果，向团队提交审阅

## Suggested Schedule

| 日期 | 任务 | 里程碑 |
|---|---|---|
| 11-04 至 11-05 | Task 1–2 | 输入、split 和数据 loader 固定 |
| 11-05 至 11-07 | Task 3–4 | 核心算法与双 \(\alpha\) 基线 |
| 11-07 至 11-10 | Task 5 | 6 点校准网格与 H5 |
| 11-10 至 11-14 | Task 6 | 空响应、案例与排除审计 |
| 11-14 至 11-16 | Task 7 | 图表和主表 |
| 11-16 至 11-23 | Task 8 | 1b/2b/3b 草稿与 H7 |

## Risks and Mitigations

| 风险 | 影响 | 缓解措施 |
|---|---|---|
| `a` 与 \(\alpha\) 被混用 | 指标和阈值含义错误 | 固定 \(a=1\)，\(\alpha\) 只用于 conformal level，并在结果 schema 中显式记录 |
| calibration 比例文档冲突 | 网格结果无法与 A/C 比较 | 已确认使用 `{0.5,0.75,1.0}`，并同步计划、手册和配置 |
| calibration pool 只有 20、test 只有 25 | 阈值和 CI 不稳定 | 使用固定 split、seed、quantile 与 bootstrap CI，不进行多次选择后挑最好结果 |
| 空集合被当作 all-correct | factuality 虚高 | 主指标采用 all-correct nonempty，并单独报告 empty rate |
| 原始回答只覆盖最后 30 个 prompt | 案例选择受限 | 优先从 survey 的 30 条中选案例，并在报告中注明数据限制 |
| 上游未保存解析失败日志 | 无法精确报告 claim/merge 排除率 | 报告缓存中可观测的缺失，其余明确写 unknown |
| 公共绘图代码归 C | B 擅自修改导致冲突 | 先定义字段需求并交给 C；B 只在 B 目录实现结果汇总，不改 `common/` |

## Open Questions

1. 仓库 README 写提交日期为 2026-11-30，但学业总账仍记为待定；需要在用户确认后更新总账，不能静默改 DDL。
2. “empty”采用“0 条 retained claims”的定义；若团队希望按最终生成文本为空来定义，需要统一修改指标与结果字段。
3. 是否允许用 `out/factscore_survey.json` 恢复最后 30 个 prompt 的原始回答开展案例研究；当前计划默认允许，并要求在报告中说明适用范围。

