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

## 计划中的模块（尚未实现）

| 文件 | 作用 |
|---|---|
| `01_baseline.py` | 从缓存分数跑双 α 基线 |
| `02_grid.py` | α × 校准比例网格 |
| `03_cases.py` | 挑成功/失败案例与空响应 |

注意：`src/factscore.py` 里的 `ALPHA` 是打分方法参数，`REQUIRED_FRAC_CORRECT` 才是 1−α。
