# Project 1 — Conformal Prediction for Reliable Short- and Long-Form QA

课程项目 · AIAA 4051 NLP (Fall 2026) · 内部计划文档（报告正文用英文）

## 0. 一页纸

| 项 | 内容 |
|---|---|
| 目标 | 复现 ConU 与 Conformal Factuality；受控对比；实现"跨回答语义一致性 claim 打分"扩展 |
| 截止 | 2026-11-30 提交；内部目标 11-28 定稿 |
| 团队 | 3 人 |
| 算力 | 学校集群；规划上限 20 GPU-hours |
| 报告 | 英文；另交代码、配置、图、poster、贡献声明 |

核心命题：**覆盖一个正确答案（coverage）** 与 **保证保留内容全对（factuality）** 是两种不同的"可靠"，
数值不可互换。整份报告围绕这条线展开。

## 1. 时间表

| 周 | 日期 | 里程碑 | 当周冻结 |
|---|---|---|---|
| W1 | 10-29 ~ 11-04 | 两个 repo 跑通最小闭环；ConU 过滤审计；模型/数据定档 | 模型、数据规模、正确性判据 |
| W2 | 11-05 ~ 11-11 | 全量子集 baseline；Part 2 案例收集；扩展用生成数据先落地 | judge prompt、判据阈值 |
| W3 | 11-12 ~ 11-18 | α × 校准集比例 网格；两张 tradeoff 图 | 实验网格 |
| W4 | 11-19 ~ 11-25 | 扩展实现与对比；**全部数字冻结** | 结果表 |
| W5 | 11-26 ~ 11-30 | 报告、poster、贡献声明、代码整理 | 提交 |

**硬性内部 deadline：11-25 之后不再跑新实验，只写。**

## 2. 分工

| 成员 | 主线 | 具体交付 |
|---|---|---|
| A | ConU | Part 1 短答案复现；Part 2 短答案失败案例 + 未过滤评估；Part 3 ConU 侧网格 |
| B | Factuality | Part 1 长回答复现；Part 2 长回答案例 + 空响应分析；Part 3 factuality 侧网格 |
| C | 基础设施 + 扩展 | 共享 metrics / 画图 / 结果汇总；Part 4 扩展；报告整合与复现检查 |

规则：

- 每人实验必须用 `src/confqa/common/metrics.py` 出数，**禁止手抄数字**。
- 每周一次 30 分钟同步，只过"本周数字 + 卡点"。
- 写作按 Part 分：A 写 1a/2a/3a，B 写 1b/2b/3b，C 写 Part 4 + Intro/Related/Conclusion，最后统一改。

## 3. 已锁定

| 决策 | 取值 | 备注 |
|---|---|---|
| 推理模型 | 一个 7–8B instruct（W1 定档） | 全项目唯一模型 |
| TriviaQA 规模 | 500 题 | 够画曲线，跑得完 |
| FActScore 规模 | repo 自带 biography prompts 全量 | 以数据文件为准 |
| α | 0.1 / 0.2 | 即 1−α = 0.9 / 0.8 |
| 额外因子 | 校准集比例 0.2 / 0.3 / 0.5 | 不需重新生成 |
| 主指标 | coverage、set size；all-correct、retention、empty | 定义见 metrics.py |

## 4. 待定（W1 内必须定）

1. 集群：调度器（SLURM?）、GPU 型号、conda 方式、存储配额
2. 模型权重：Llama-3.1-8B（需 HF 授权）还是 Qwen2.5-7B（免授权）
3. ConU 的 correctness 判据：沿用 repo 的相似度阈值 0.6，还是叠加人工抽查
4. Factuality 的 judge：哪个模型、prompt 固定成什么、人工校验多少条

## 5. 关键风险与止损

| 风险 | 触发信号 | 止损动作 |
|---|---|---|
| ConU 过滤偏差导致 coverage 复现不出来 | 未过滤 coverage 明显低于论文 | 把它本身写成 Part 2 的发现 |
| claim 标注太贵 | 人工标注 > 3 天 | 降级为 judge + 50 条人工校验，报一致率 |
| 扩展无提升 | W4 中旬仍无正向信号 | 改报"重复即正确"的失效分析 |
| 集群排队 | 单 job 等待 > 1 天 | 提前批量提交，多个 config 合成数组 job |
| 三人进度不同步 | 周会拿不出数字 | 每天 push 一个 results json |

## 6. 交付物 checklist

- [ ] 代码（一键复现）
- [ ] 配置 yaml + 固定 seed
- [ ] 结果表：coverage/size；all-correct/retention/empty；双 α × 校准比例
- [ ] 两张 tradeoff 图 + 扩展对比图
- [ ] 成功/失败案例各若干
- [ ] 英文报告
- [ ] poster
- [ ] 个人贡献声明

## 7. 数字纪律

1. 所有数字来自 `exp/results/*.json`，由脚本写入。
2. 报告每张表标注生成它的 config 文件名。
3. 校准/开发/测试三份数据固定，切分文件放 `data/splits/`，记录 hash。
4. 任何"手工调整"在下表留一行。

## 8. 决策记录

| 日期 | 决策 | 理由 | 影响 |
|---|---|---|---|
| 10-29 | 采用 src 布局 + `confqa` 包，CI 只跑 stdlib 测试 | 集群登录节点也要能跑测试 | 重依赖隔离在 requirements-gpu.txt |
