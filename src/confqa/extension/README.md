# extension — Part 4 跨回答一致性 claim 打分

**Owner: C** · 手册：[docs/manuals/C-infra-extension.md](../../../docs/manuals/C-infra-extension.md)

## 与 baseline 的区别

| | baseline（上游 frequency） | 扩展 |
|---|---|---|
| 等价性判定 | LLM judge（support / contradict / unrelated） | embedding 语义聚类 |
| 采样预算 | 5 个回答 | 5 个回答 |
| 分数 | 支持数之和 | 含等价 claim 的回答比例 |

## 数据流

```
cache/ext_responses.jsonl        ← 50 prompt × 5 response（只生成一次）
cache/ext_claims.jsonl           ← claim 拆分结果
cache/ext_clusters.jsonl         ← 聚类与 support
exp/results/ext__a<alpha>__calib<ratio>.json
```

**关键**：baseline 也必须在我们自己的 5 条回答上重跑，不能拿上游缓存的数字对比。
