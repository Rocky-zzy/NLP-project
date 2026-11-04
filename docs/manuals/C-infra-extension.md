# 实验手册 · C · 基础设施 + 扩展

标记约定（三份手册统一）：

- **【原文】** 项目描述里的原话，后面括号标出处（Objectives / Codebases / Part N / Deliverables）
- **【团队】** 我们三个人已经定下的事，项目没有强制，可以改但要三人同意
- **【建议】** 操作层面的提醒，随时可改


## 0. 你负责什么

你负责两件性质不同的事：

1. **让 A 和 B 的数字可比、可追溯**（团队安排，项目没有直接要求，但它的依据是下面几条硬约束）
2. **Part 4 的扩展**（项目原文明确要求）

| 你的产出 | 出自 |
|---|---|
| 固定切分、结果模板、图表 | 【原文】校准/测试分离等约束 |
| 扩展方法 + 对比实验 | Part 4 |
| 报告 Part 4 + 统稿 | Deliverables |

---

## 1. 时间线

| 天 | 任务 | 交给谁 |
|---|---|---|
| 1–2 | C1 环境协助 | — |
| 2–4 | C2 切分 + 结果模板 + 画图骨架 | H2 → A,B |
| 4–6 | C3 250 条生成 | — |
| 6–10 | C4 claim 拆分 + baseline 打分 | — |
| 10–13 | C5 扩展打分 + 校准 | — |
| 13–16 | C6 对比 + 失败分析 | H6 → A,B |
| 16–24 | C7 统稿 + poster | — |

---

## 2. 任务

### C1 · 环境协助（第 1–2 天）

**非原文要求**，是团队安排。你不需要先配好再交给 A，而是和 A 一起弄：两个人排错比一个人快，而且你第 4 天就要用同一个 vLLM。

**完成标准**：你能独立起服务。

---

### C2 · 切分 + 结果模板（第 2–4 天）

【原文 · Part 3】"Keep test examples separate from calibration and any parameter tuning."
【原文 · Computational scope】"Keep calibration, development, and test examples disjoint."
【原文 · Computational scope】"Select these prompts before inspecting model outcomes."

**做什么**
1. 生成 `data/splits/`：TriviaQA 500 题、FActScore 50 个 prompt，各切出 calib / dev / test，写 json + sha256
2. 写 `run_result()`：每次实验把 alpha、calib_ratio、model、seed、git commit 写进同一个 json
3. 写两张图的画图函数骨架

**输出**：切分文件进仓库；A/B 拿到同一批 id。

**完成标准**：A 和 B 用你的切分跑出来的 json，分母完全一致。

**注意**：prompt 必须在看模型输出**之前**就选好，这是原文明确写的。

---

### C3 · 250 条生成（第 4–6 天）

【原文 · Computational scope】"For the supplementary generation and combination study, use at most 50 prompts per setting and up to five responses per prompt."
【原文 · Computational scope】"Fix one inference model for any new local generations."
【原文 · Part 4】"Generate several responses to the same question and decompose them into claims."

**做什么**：50 个 prompt × 5 个回答，温度 1.0，复用 A 的 vLLM，落 `cache/ext_responses.jsonl`

**完成标准**：正好 50 × 5，不多不少；prompt 列表在生成前就冻结并记录。

**别做**：不要因为某题生成得不好看就换题——原文要求先选题再看结果。

---

### C4 · claim 拆分 + baseline 打分（第 6–10 天）★ 风险最高

【原文 · Part 4】"Compare this extension with an existing claim-scoring method at the same sampling budget."

**关键理解**：上游缓存的 `frequency-score` 是 GPT-4 在**它自己的 5 个样本**上算的。要"same sampling budget"，你必须用**我们自己的 250 条**重新跑一遍原方法。

**做什么**
1. 用上游的 breakdown prompt 把 250 条回答拆成 claim
2. 用 LLM judge 对每条 claim 在 5 个回答里判 support / contradict / unrelated，得到原方法的分数
3. 把 judge 换成 vLLM 本地模型（OpenAI-compatible），记录模型名和 prompt hash

**输出**：`cache/ext_claims.jsonl`、`cache/ext_baseline_scores.jsonl`

**完成标准**：解析失败率 < 5%，失败样本单独记录；抽样 20 条人工核对 judge 判断。

**止损**：如果第 8 天还在和 JSON 解析搏斗，就降到 25 个 prompt，保证有结果。

---

### C5 · 扩展打分 + 校准（第 10–13 天）

【原文 · Part 4】
> "Use semantic similarity to identify equivalent claims across responses."
> "Score each claim by the proportion of responses containing an equivalent claim."
> "Use these scores in the conformal factuality filtering procedure and recalibrate its threshold."

**做什么**
1. 对跨回答的 claim 做语义聚类（embedding + 阈值）
2. support = 含等价 claim 的回答数 / 5
3. 用 support 当分数，重跑 conformal 校准，α = 0.1 / 0.2

**输出**：`cache/ext_clusters.jsonl`、`exp/results/ext__a0.1__calib0.5.json`

**完成标准**：和 baseline 用同一批 prompt、同一个 α、同一个校准比例，唯一变量是打分方式。

---

### C6 · 对比与失败分析（第 13–16 天）

【原文 · Part 4】"Investigate whether it retains more useful claims at comparable factuality, and examine failures caused by repeated but incorrect claims."
【原文 · Part 4】"A well-executed negative result is acceptable."

**做什么**
1. 画 baseline 与扩展的 retention–factuality 对比图
2. 统计"高 support 但实际错误"的 claim 比例 —— 这是"重复即正确"失效的直接证据

**完成标准**：不管结果是正是负，都能回答"同等 factuality 下，谁保留了更多 claim"。

**提醒**：负结果是允许的，但必须给出机制解释；"没提升"三个字不算结论。

---

### C7 · 统稿 + poster（第 16–24 天）

【原文 · Deliverables】"a report covering motivation, methods, experimental setup, results, failure analysis, and conclusions, together with runnable code, configurations, plots, a poster, and individual contribution statements."

**你写**：Intro、Related Work、Part 4、Conclusion；汇总所有表；排 poster；收贡献声明。

**完成标准**：报告里每一张图都能用仓库里的脚本重新生成。

---

## 3. 交接

| 编号 | 时间 | 交给谁 | 交什么 |
|---|---|---|---|
| H1 | 11-06 | 收 A | vLLM 启动方式 |
| H2 | 11-07 | 给 A,B | 切分 + sha256 + run_result 模板 |
| H3 | 11-08 | 收 B | claim 拆分与校准入口 |
| H4 | 11-10 | 收 A | 相似度/embedding 用法 |
| H6 | 11-20 | 给 A,B | 统一图表 + 汇总表 |
| H7 | 11-23 | 收 A,B | 三份草稿 |

---

## 4. 禁止事项

1. 不写 A/B 的章节（统稿不是代写）
2. 不超过 50 prompt × 5 response
3. 不在看过结果之后更换 prompt 子集
4. 不把 50 个 prompt 上的结果说成"覆盖保证"
5. 不在第 4 周新建框架，够用就行

---

## 5. 验收清单

- [ ] 切分文件 + sha256 已提交
- [ ] 50 × 5 生成完成且 prompt 列表冻结
- [ ] baseline 在**我们自己的** 5 条上重跑完成
- [ ] 扩展打分与校准完成
- [ ] 对比图 + "重复但错误"的统计
- [ ] 报告 Part 4 + 统稿 + poster
