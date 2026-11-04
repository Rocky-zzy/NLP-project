# conu — ConU 短问答管线

**Owner: A** · 手册：[docs/manuals/A-conu.md](../../../docs/manuals/A-conu.md)
上游：`third_party/ConU` @ `c0c450e`（见 [docs/reference/upstream_versions.md](../../../docs/reference/upstream_versions.md)）

## 数据流

```
cache/conu_generations.jsonl   ← 采样结果（只生成一次）
cache/conu_scores.jsonl        ← 相似度与正确性标记
exp/results/conu__a<alpha>__calib<ratio>.json
```

字段定义见 [docs/reference/schemas.md](../../../docs/reference/schemas.md)。

## 计划中的模块（尚未实现）

| 文件 | 输入 | 输出 |
|---|---|---|
| `01_generate.py` | TriviaQA 子集 | `conu_generations.jsonl` |
| `02_similarity.py` | 生成结果 | `conu_scores.jsonl` |
| `03_conformal.py` | 分数 | `exp/results/*.json` |
| `audit_no_filter.py` | 分数 | 过滤前后对照表 |

上游脚本保持原样，通过 CLI 参数覆盖模型与数据路径；需要改变行为时写 `patches/`，不改 `third_party/`。
