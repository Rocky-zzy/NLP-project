# factuality — Conformal Factuality 长回答管线

**Owner: B** · 手册：[docs/manuals/B-factuality.md](../../../docs/manuals/B-factuality.md)
上游：`third_party/conformal-factual-lm` @ `6022b4c`

## 数据流

```
data/factscore_annotations.jsonl        ← 50 个 prompt 的人工标注（上游自带）
out/factscore_subclaims_with_scores.jsonl ← 所有打分方法的分数（上游自带）
exp/results/fact__a<alpha>__calib<ratio>.json
```

主线实验只读缓存，不需要 GPU 也不调用 API。

## 已实现的模块

| 文件 | 作用 |
|---|---|
| `data.py` | 读取 wrapped JSON、生成稳定 ID、对齐固定 split |
| `conformal.py` | rank score、有限样本阈值和 claim filtering |
| `evaluate.py` / `cli.py` | 双 alpha 基线、校准比例网格和案例统计 |
| `cases.py` | 原始回答恢复、成功/失败案例与排除审计 |
| `report.py` | 从 result JSON 生成带 CI 的 retention–factuality 图 |

输入哈希和已知数据限制见
[`docs/reference/factscore-inputs.md`](../../../docs/reference/factscore-inputs.md)。

注意：上游 `ALPHA` 是 conformal 错误率，`REQUIRED_FRAC_CORRECT`（paper 中的
\(a\)）是每条回答要求正确保留的比例。课程要求全部保留 claim 正确，因此主实验
固定 \(a=1\)，并研究 \(\alpha=0.1/0.2\)。
