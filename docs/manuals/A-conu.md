# 实验手册 · A · ConU 线

标记约定（三份手册统一）：

- **【原文】** 项目描述里的原话，后面括号标出处（Objectives / Codebases / Part N / Deliverables）
- **【团队】** 我们三个人已经定下的事，项目没有强制，可以改但要三人同意
- **【建议】** 操作层面的提醒，随时可改


## 0. 你负责什么

【原文 · Objectives】"Reproduce two conformal methods for language generation."

两条方法里你负责短问答那一半，外加围绕它的分析与写作。

| 你的产出 | 出自 |
|---|---|
| ConU 复现，报告 coverage 与 set size | Part 1 |
| 过滤偏差审计 + 未过滤评估 | Part 2 |
| 双 α × 一个额外因子的短问答实验 | Part 3 |
| 报告 1a / 2a / 3a 节 | Deliverables |

【原文 · Codebases】"Short-form QA: ConU repository, using a subset of TriviaQA."

---

## 1. 时间线

| 天 | 任务 | 交给谁 |
|---|---|---|
| 1–2 | A1 环境与模型 | H1 → C |
| 2–4 | A2 五步跑通（100 题） | — |
| 4–6 | A3 全量 500 题 + 相似度 | H4 → C |
| 6–8 | A4 过滤审计 | — |
| 8–11 | A5 α × 校准比例网格 | H5 → C |
| 11–15 | A6 成功/失败案例 | — |
| 15–21 | A7 写 1a/2a/3a | H7 → C |

---

## 2. 任务

### A1 · 环境与模型（第 1–2 天）

【原文 · Computational scope】"Fix one inference model for any new local generations."
【原文 · Recommended scope】"Hardware: 1 × NVIDIA A6000."

**做什么**
1. 在集群装 torch / transformers / vllm，下载模型权重
2. 起 vLLM 的 OpenAI-compatible server，确认一次对话能返回
3. 把命令写进 `scripts/setup_env.sh`，把启动命令写进 `docs/upstream_versions.md` 的末尾

**团队决定**：模型用 Qwen2.5-14B-Instruct（和上游脚本默认一致、不需要 HF 授权、A6000 放得下）。

**输出**：C 拿到就能起服务的脚本，而不是口头说明。

**完成标准**：C 在你不参与的情况下，照脚本能起服务并跑通一次请求。

**别做**：不要在这里顺手改上游代码，路径全部用 CLI 覆盖。

---

### A2 · 跑通 ConU 五步（第 2–4 天，先 100 题）

【原文 · Part 1】"Run the ConU pipeline: sample answers, compute uncertainty scores, calibrate a threshold, and construct answer sets."

**做什么**：按上游顺序跑通五个脚本，先 100 题。

```bash
python parse_triviaqa.py --few-shot-num 3 --max-num 100
python generate.py --generate-model <你的模型路径> ...
python clean_open_domain_qa.py --dataset triviaqa ...
python open_domain_qa_similarity.py --dataset triviaqa ...
python conformal_uncertainty_criterion.py --dataset triviaqa ... \
       --split-ratio 0.5 --correctness-threshold 0.6 --alpha 0.1
```

**三个必须注意的坑**
1. 上游 README 的命令顺序里 `clean_open_domain_qa.py` 出现了两次，实际应该是 `parse → generate → clean → similarity → conformal`，自己确认一遍。
2. `--correctness-threshold` 脚本默认 0.7，README 示例是 0.6。**永远显式传**，并把值写进结果 json。
3. `conformal_uncertainty_criterion.py:77` 硬编码 `CUDA_VISIBLE_DEVICES = '0,1'`，必须改成单卡。

**输出**：`cache/conu_generations.jsonl`、`cache/conu_scores.jsonl`（格式见 `docs/schemas.md`）

**完成标准**：脚本能打印 Applied / Calibration / Test 三个数量，并给出 coverage 与 average set size。

---

### A3 · 全量 500 题（第 4–6 天）

【原文 · Codebases】"using a subset of TriviaQA."
【原文 · Part 1】"Reproduce one representative result from each repository on a manageable subset."

**团队决定**：500 题。取法是固定的（例如按 qid 排序取前 500），不能挑。

**输出**：覆盖 500 题的 `conu_generations.jsonl` 与 `conu_scores.jsonl`

**完成标准**：C 能用同一批 qid 复现你的题集。

**别做**：不要按模型表现筛题，这就是 Part 2 要审计的那个偏差。

---

### A4 · 过滤审计（第 6–8 天）★ 本项目最容易拿分的一项

【原文 · Part 2】"In particular, the ConU implementation filters out examples without an acceptable sampled answer before splitting the data. Report the excluded proportion and examine performance on the unfiltered examples as well."

**做什么**
1. 在 `conformal_uncertainty_criterion.py:88-94` 确认过滤发生在 `:97` 的 split 之前
2. 写一份 patch 放到 `patches/`，加一个"不过滤"的开关（`third_party/` 保持原样，运行前复制再打补丁）
3. 同一批数据跑两遍：过滤版、未过滤版

**输出**：一张表，至少包含

| 列 | 含义 |
|---|---|
| n_total | 原始题数 |
| n_used | 过滤后题数 |
| n_dropped / pct | 被删掉的数量与比例 |
| coverage_filtered | 过滤版 |
| coverage_unfiltered | 未过滤版 |
| set_size 两版 | 各一行 |

**完成标准**：两个 coverage 出现在同一张表里，分母写得清清楚楚。

**别做**：不要只报过滤后的数字；也不要把"过滤后更好看"当成结果。

---

### A5 · Part 3 网格（第 8–11 天）

【原文 · Part 3】"Evaluate two target levels, such as 1 − α = 0.8 and 0.9."
【原文 · Part 3】"Investigate one additional factor: the number of sampled responses, calibration-set size, or response length."
【原文 · Part 3】"Visualize the tradeoff between reliability and usefulness: answer-set size for short-form QA, and retained information for long-form generation."
【原文 · Part 3】"Keep test examples separate from calibration and any parameter tuning."

**团队决定**：额外因子选**校准集大小**（0.2 / 0.3 / 0.5）。理由：不用重新生成，改 split 比例即可。

**做什么**：6 个配置 = 2 个 α × 3 个校准比例，全部复用 A3 的采样结果。

**输出**：`exp/results/conu__a0.1__calib0.5.json` 这样的 6 个文件，字段照 `docs/schemas.md`；一张 coverage–set size 图。

**完成标准**：每个点带 bootstrap 置信区间（用 `src/confqa/common/metrics.py` 里的函数）。

**别做**：不要用测试集调 α 或阈值，那是数据泄漏。

---

### A6 · 成功与失败案例（第 11–15 天）

【原文 · Part 2】"Present several successful and unsuccessful examples."
【原文 · Part 2】"What happens when repeated sampling never produces a correct answer?"
【原文 · Part 2】"Why might a set of alternative answers be useful for short-form QA?"

**做什么**：至少各 2 例，每例保留
- 原问题与标准答案
- 20 个采样原文
- 最终答案集合
- 每个采样和标准答案的相似度
- 一句话说明"这个例子说明了什么"

**完成标准**：案例里能直接看出"集合救回来了"或"20 次采样全错"。

---

### A7 · 写作（第 15–21 天）

【原文 · Part 1】"Explain the input, output, calibration procedure, and correctness criterion of each method."
【原文 · Part 1】"Report answer-set coverage and size for ConU."

**你写**：1a（复现）、2a（短问答分析 + 审计）、3a（短问答网格）。

**完成标准**：每个数字后面标着生成它的 `exp/results/*.json` 文件名；每个方法的输入、输出、校准过程、正确性判据四件事都写清楚。

---

## 3. 交接

| 编号 | 时间 | 交给谁 | 交什么 |
|---|---|---|---|
| H1 | 11-06 | C | vLLM 启动脚本、模型路径、显存参数 |
| H4 | 11-10 | C | embedding 模型、相似度算法、阈值在哪一行 |
| H5 | 11-15 | C | `exp/results/*.json` 第一批 |
| H7 | 11-23 | C | 1a/2a/3a 草稿 |

---

## 4. 禁止事项

1. 不改 `third_party/ConU` 的源码；要改行为就写 patch，并在报告里说明改了什么
2. 不按模型表现挑题
3. 不把 calibration 和 test 混用
4. 不在报告里手抄数字
5. 不用论文里的数字冒充自己的复现结果

---

## 5. 验收清单

- [ ] 五步管线能从零跑通，命令记录在案
- [ ] 500 题的 coverage 与 set size，带置信区间
- [ ] 过滤比例，以及过滤前后的 coverage 对照表
- [ ] 6 个网格结果 json + 一张 tradeoff 图
- [ ] 成功案例 ≥ 2，失败案例 ≥ 2
- [ ] 1a/2a/3a 三节草稿
