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

输入哈希和已知数据限制见
[`docs/reference/factscore-inputs.md`](../../../docs/reference/factscore-inputs.md)。

## 后续模块

| 文件 | 作用 |
|---|---|
| `evaluate.py` / `cli.py` | 从缓存分数跑双 α 基线与校准比例网格 |
| `cases.py` | 挑成功/失败案例与空响应 |
| `report.py` | 生成报告主表和图 |

注意：`src/factscore.py` 里的 `ALPHA` 是打分方法参数，`REQUIRED_FRAC_CORRECT` 才是 1−α。
