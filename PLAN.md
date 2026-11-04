# PLAN — 项目级状态页

- 周计划与交接点：[docs/planning/workplan.png](docs/planning/workplan.png)
- 个人任务：[docs/manuals/](docs/manuals/)
- 工件格式：[docs/reference/schemas.md](docs/reference/schemas.md)

这个文件只保留**目标、约束、决策、风险**。周计划和分工细节已经移到上面两处，不在这里重复。

## 1. 目标

复现 ConU 与 Conformal Factuality 两条方法，比较"覆盖一个正确答案"与"控制保留内容的真实性"这两种可靠性定义，
再实现并评估一个把两者思路结合的小扩展。

## 2. 硬约束（项目原文）

- 一个数据集、一个推理模型
- 规划算力 20 GPU-hours，不做训练
- 主实验用缓存输出与现有标注；新生成仅作补充
- 补充生成 ≤ 50 prompt × ≤ 5 response，且 prompt 要在看结果前选好
- 校准 / 开发 / 测试三份数据必须分离
- 双目标水平 1−α = 0.9 与 0.8
- 报告用英文；交付代码、配置、图、poster、个人贡献声明

## 3. 分工

| 人 | 范围 | 代码目录 | 手册 |
|---|---|---|---|
| A | ConU 短问答 | `src/confqa/conu/` | [A-conu](docs/manuals/A-conu.md) |
| B | 长回答 | `src/confqa/factuality/` | [B-factuality](docs/manuals/B-factuality.md) |
| C | 基础设施 + 扩展 | `src/confqa/common/`, `src/confqa/extension/` | [C-infra-extension](docs/manuals/C-infra-extension.md) |

## 4. 已锁定决策

| 决策 | 取值 | 备注 |
|---|---|---|
| 推理模型 | Qwen2.5-14B-Instruct | 与上游默认一致、无需 HF 授权、A6000 放得下 |
| TriviaQA 规模 | 500 题，固定取法 | 不按模型表现挑题 |
| FActScore 规模 | repo 自带 50 个 prompt | 标注与分数均已缓存 |
| α | 0.1 / 0.2 | 即 1−α = 0.9 / 0.8 |
| 额外因子 | 校准集比例 0.2 / 0.3 / 0.5 | 复用缓存，零额外生成 |

## 5. 风险与止损

| 风险 | 触发信号 | 止损动作 |
|---|---|---|
| ConU 过滤偏差导致 coverage 复现不出来 | 未过滤 coverage 明显低于论文 | 把它本身写成 Part 2 的发现 |
| 扩展的 JSON 解析迟迟搞不定 | W4 中旬仍无干净结果 | 降到 25 个 prompt，保证有结论 |
| 扩展无提升 | W4 中旬仍无正向信号 | 改报"重复即正确"的失效分析 |
| 集群排队 | 单 job 等待 > 1 天 | 多个 config 合成数组 job |
| 三人进度不同步 | 周会拿不出数字 | 每天 push 一个 results json |

## 6. 交付物

- [ ] 代码（一键复现）
- [ ] 配置 yaml + 固定 seed
- [ ] 结果表：coverage/size；all-correct/retention/empty；双 α × 校准比例
- [ ] tradeoff 图 + 扩展对比图
- [ ] 成功/失败案例
- [ ] 英文报告
- [ ] poster
- [ ] 个人贡献声明

## 7. 决策记录

| 日期 | 决策 | 理由 | 代价 |
|---|---|---|---|
| 10-29 | 采用 src 布局 + `confqa` 包，CI 只跑 stdlib 测试 | 集群登录节点也要能跑测试 | 重依赖隔离在 requirements-gpu.txt |
| 11-04 | 额外因子定为校准集大小，不选采样数 | 复用缓存，不动 GPU | 采样数 K 的效应留作 future work |
| 11-04 | 目录按 A/B/C 重组；docs 分 manuals / planning / reference | 三个人并行时按人找东西 | 新增文档必须放进对应子目录 |
