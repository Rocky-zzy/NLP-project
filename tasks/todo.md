# B 部分执行清单

详细验收标准、依赖和风险见 [plan.md](plan.md)。

## Phase 1: 数据与核心

- [x] Task 1：固定上游 commit、输入哈希与数据限制（11-05）
- [x] Task 2：实现 FActScore loader 与 split 对齐（11-05）
- [x] Task 3：移植 conformal factuality 核心算法（11-07）
- [x] Checkpoint：上游输入、loader 和核心算法测试全部通过

## Phase 2: 主实验

- [x] Task 4：生成 `alpha=0.1/0.2`、`calib_frac=0.5` 的基线结果（11-07）
- [x] Task 5：生成 2 个目标水平 × 3 个校准比例的 6 个结果（11-10）
- [x] Checkpoint：6 个 JSON 均为 `reportable=true`，字段和 split hash 可追溯

## Phase 3: 分析与交付

- [x] Task 6：完成 empty rate、过度删减、成功案例与排除审计（11-14）
- [x] Task 7：生成 retention–factuality 图和汇总表（11-16）
- [ ] Task 8：完成 1b/2b/3b 英文草稿与 H3/H5/H7 交接（11-23）
- [ ] Checkpoint：全量测试、lint、干净环境复跑和 C 独立复现均通过

## 必须拍板

- [x] 校准比例采用 `{0.5, 0.75, 1.0}`
- [ ] `empty` 是否按“0 条 retained claims”定义
- [ ] 是否确认最终 DDL 为 2026-11-30 并同步学业总账
