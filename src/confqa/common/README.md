# common — 共享工具

**Owner: C**（其他人可以读，改动前先说一声）

| 模块 | 作用 |
|---|---|
| `metrics.py` | coverage、set size、all-correct、retention、empty rate、bootstrap CI |
| `io.py` | jsonl / json / yaml 读写 |
| `paths.py` | 仓库内固定路径，不依赖当前目录 |
| `seed.py` | 统一随机种子 |

规则：**报告里的每个数字都必须来自 `metrics.py`**，不接受手工计算或从别处抄。
