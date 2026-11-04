# 实验手册 · B · Conformal Factuality 线

标记约定（三份手册统一）：

- **【原文】** 项目描述里的原话，后面括号标出处（Objectives / Codebases / Part N / Deliverables）
- **【团队】** 我们三个人已经定下的事，项目没有强制，可以改但要三人同意
- **【建议】** 操作层面的提醒，随时可改


## 0. 你负责什么

【原文 · Objectives】"Understand the distinction between covering a correct answer and controlling the factuality of retained claims."

你负责长回答那一半。和 A 的短问答线并列，两边最后要放在同一份报告里对比。

| 你的产出 | 出自 |
|---|---|
| conformal factuality 复现 | Part 1 |
| 长回答失败分析 + 空响应 | Part 2 |
| 双 α × 一个额外因子 | Part 3 |
| 报告 1b / 2b / 3b 节 | Deliverables |

【原文 · Codebases】"Long-form generation: Conformal factuality repository, using FActScore biography prompts. The repository includes annotated claims and saved outputs that can support initial reproduction."

**好消息**：`data/factscore_annotations.jsonl` 自带 50 个 prompt 的人工标注，`out/factscore_subclaims_with_scores.jsonl` 自带所有打分方法的分数。**主线实验不需要 GPU，也不需要 API。**

---

## 1. 时间线

| 天 | 任务 | 交给谁 |
|---|---|---|
| 1–2 | B1 读代码 + 缓存出数 | — |
| 2–4 | B2 双 α 基线 | — |
| 4–8 | B3 案例 + 空响应分析 | H3 → C |
| 8–11 | B4 α × 校准比例网格 | H5 → C |
| 11–15 | B5 出图 + 表 | — |
| 15–21 | B6 写 1b/2b/3b | H7 → C |

---

## 2. 任务

### B1 · 读代码 + 用缓存出第一批数（第 1–2 天）

【原文 · Codebases】"Students may begin with cached outputs and then generate a small collection of new responses."

**做什么**
1. 读 `third_party/conformal-factual-lm/src/calibrate_thresh.py` 里 `analyze_dataset` 的签名和返回
2. 用 `out/factscore_subclaims_with_scores.jsonl` 跑 `confidence_method = frequency / gpt / optimal`
3. 先不看论文数字，自己算一遍

**输出**：第一版表，α = 0.1 / 0.2 下三个数

【原文 · Part 1】"report the proportion of responses whose retained claims are all correct, the proportion of original claims retained, and the frequency of empty responses."

**完成标准**：三个指标都能算出来，且和自己手算的一两个样本对得上。

**坑**：上游 `ALPHA` 是 conformal 错误率，`REQUIRED_FRAC_CORRECT`（即 paper 中的 \(a\)）是每条回答要求正确保留的比例，两者不同。课程要求保留 claim 全部正确，因此主实验固定 \(a=1\)，研究 \(\alpha=0.1/0.2\)，即 \(1-\alpha=0.9/0.8\)。

---

### B2 · 双 α 基线（第 2–4 天）

【原文 · Part 3】"Evaluate two target levels, such as 1 − α = 0.8 and 0.9."

**做什么**：同一份缓存，跑 1−α = 0.9 和 0.8 两档，固定 confidence method 为 `frequency`（团队决定）。

**输出**：`exp/results/fact__a0.1__calib0.5.json` 等，字段照 `docs/reference/schemas.md`

**完成标准**：随着 α 变小（要求更严），retention 应下降、empty rate 应上升。`all-correct nonempty` 以全部回答为分母时可能因删空而下降，因此还要同时检查非空回答中的条件全对率和 bootstrap CI。

---

### B3 · 案例与空响应（第 4–8 天）

【原文 · Part 2】"Why might claim filtering be more useful for a long response containing both correct and incorrect claims?"
【原文 · Part 2】"Can filtering make a response factually correct but too incomplete to answer the question?"
【原文 · Part 2】"Present several successful and unsuccessful examples."

**做什么**
1. 找 ≥2 个"过滤后事实全对，但内容已经不足以回答提问"的例子
2. 找 ≥2 个"过滤救回了大部分正确信息"的例子
3. 统计空响应的比例，并看它们长什么样

**完成标准**：每个例子给出原始回答、保留下来的 claim、删掉的 claim、以及一句判断"还能不能回答问题"。

【原文 · Part 2】"Inspect whether either implementation excludes difficult examples."

**额外任务**：确认长回答这条线**有没有**类似的样本排除（比如拆不出 claim 的、merge 失败的）。如果有，同样报比例。这条原文说的是 "either implementation"，所以两边都要查，你查长回答这边。

---

### B4 · α × 校准比例网格（第 8–11 天）

【原文 · Part 3】"Investigate one additional factor: the number of sampled responses, calibration-set size, or response length."
【原文 · Part 3】"Visualize the tradeoff between reliability and usefulness: ... retained information for long-form generation."

**团队决定**：额外因子用 calibration pool 的 0.5 / 0.75 / 1.0，即 10 / 15 / 20 条回答，和 A 的配置一致。

**输出**：6 个结果 json + 一张 retention–factuality 图（横轴保留率，纵轴全对比例，两个 α 两组曲线）

**完成标准**：图上能看出"多删一点换更高正确率"的曲线形状，且每个点有置信区间。

---

### B5 · 出图与汇总表（第 11–15 天）

【原文 · Deliverables】"runnable code, configurations, plots"

**做什么**：把 B 的所有数字汇总成一张主表（α × 校准比例 × 三个指标），配两张图。

**完成标准**：A 拿到你的表就能直接做"短 vs 长"的对比，不需要再问你。

---

### B6 · 写作（第 15–21 天）

**你写**：1b（复现，含输入/输出/校准/正确性判据四件事）、2b（长回答分析 + 空响应 + 是否排除难例）、3b（网格）。

【原文 · Part 1】"Explain the input, output, calibration procedure, and correctness criterion of each method."

**完成标准**：每个数字标着来源文件；明确写出"factuality 高但信息少"是这套方法的固有代价。

---

## 3. 交接

| 编号 | 时间 | 交给谁 | 交什么 |
|---|---|---|---|
| H3 | 11-08 | C | claim 拆分与阈值校准的函数入口 + 示例输出 |
| H5 | 11-15 | C | `exp/results/*.json` 第一批 |
| H7 | 11-23 | C | 1b/2b/3b 草稿 |

H3 的完成标准很具体：**C 用一个你不参与的目录，能跑出同样格式的结果**。

---

## 4. 禁止事项

1. 不重新标注 claim（标注已自带）
2. 不用 GPT-4 重跑主实验换取"更漂亮"的数字——主实验就是复现缓存
3. 不混用不同 confidence method 的数字放在同一张表里
4. 不把 50 个 prompt 的结果说成"可靠的 factuality 保证"（原文明确：小规模补充数据不能用来声称保证）

---

## 5. 验收清单

- [ ] 三个指标在 α = 0.1 / 0.2 下都算出来了
- [ ] 6 个网格结果 json
- [ ] retention–factuality 图
- [ ] 空响应比例与典型例子
- [ ] 长回答侧是否有样本排除的结论
- [ ] 1b/2b/3b 三节草稿
