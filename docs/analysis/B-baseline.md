# B 双 alpha 基线记录

## 设置

- 输入：上游 pinned FActScore cached claims 与人工标注
- 方法：`frequency` 分数，`required_correct_fraction=1.0`
- calibration：`calib_frac=0.5`，从 20 条 pool 中固定抽取 10 条
- test：固定 25 条，与 calibration 无交集
- CI：对 test response 做 10,000 次 percentile bootstrap

## 结果

| alpha | 1-alpha | threshold | retained claims | all-correct nonempty | retention | empty rate |
|---:|---:|---:|---:|---:|---:|---:|
| 0.1 | 0.9 | 5.00007 | 34 / 210 | 15 / 25 = 0.60 | 0.1619 | 9 / 25 = 0.36 |
| 0.2 | 0.8 | 4.99876 | 62 / 210 | 20 / 25 = 0.80 | 0.2952 | 3 / 25 = 0.12 |

结果文件：

- `exp/results/fact__a0.1__calib0.5.json`
- `exp/results/fact__a0.2__calib0.5.json`

## 为什么 alpha 更小但 headline factuality 更低

alpha 更小意味着目标更严格，阈值略高，因此会删掉更多 claim。当前指标
`all_correct_nonempty` 的分子要求回答非空且保留 claim 全对，分母仍是全部
test responses。

alpha=0.1 时 25 条中有 9 条被删空，非空回答只剩 16 条，其中 15 条全对：

- 条件于非空回答的全对率：15 / 16 = 0.9375
- 以全部回答为分母的 headline：15 / 25 = 0.60

alpha=0.2 时只有 3 条被删空，非空回答有 22 条，其中 20 条全对：

- 条件于非空回答的全对率：20 / 22 = 0.9091
- 以全部回答为分母的 headline：20 / 25 = 0.80

因此这一现象来自“保留下来的内容是否可靠”和“回答是否仍然可用”之间的
权衡，不代表阈值方向算反。报告需要同时呈现 all-correct、retention 和
empty rate，不能只看一个 headline 数字。
