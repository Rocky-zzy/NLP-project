"""Render the team work plan (Gantt + handoff table) for Project 1."""

import datetime as dt

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei"]
plt.rcParams["axes.unicode_minus"] = False

START = dt.date(2026, 11, 4)


def label(off: int) -> str:
    return (START + dt.timedelta(days=off)).strftime("%m-%d")


PEOPLE = [
    ("A  ConU 线", "#3B6EA5", 2, [
        ("环境 + 模型", 0, 2),
        ("跑通 100 题", 2, 4),
        ("500 题生成", 4, 6),
        ("过滤审计", 6, 8),
        ("α 网格", 8, 11),
        ("案例 + 出图", 11, 15),
        ("写 1a-3a", 15, 21),
    ]),
    ("B  Factuality 线", "#D9822B", 1, [
        ("读代码+出数", 0, 2),
        ("双 α 基线", 2, 4),
        ("案例 + 空响应", 4, 8),
        ("α 网格", 8, 11),
        ("出图 + 表", 11, 15),
        ("写 1b-3b", 15, 21),
    ]),
    ("C  基础设施 + 扩展", "#3F8F5A", 0, [
        ("环境协助", 0, 2),
        ("切分 + 模板", 2, 4),
        ("250 条生成", 4, 6),
        ("claim + baseline", 6, 10),
        ("扩展打分", 10, 13),
        ("对比分析", 13, 16),
        ("统稿 + poster", 16, 24),
    ]),
]

HANDOFFS = [
    (2, "H1", "A→C", "vLLM 启动脚本、模型路径、显存参数", "C 能独立起服务并跑通一次对话"),
    (3, "H2", "C→A,B", "data/splits/*.json、sha256、run_result 模板", "A/B 用同一批 id 跑出同格式 json"),
    (4, "H3", "B→C", "claim 拆分与阈值校准的函数入口 + 示例输出", "C 能用同一入口跑自己的 250 条"),
    (6, "H4", "A→C", "embedding 模型、相似度算法、阈值位置", "C 能在扩展里复现同样的相似度"),
    (11, "H5", "A,B→C", "exp/results/*.json 第一批", "每个数字都能指回一个文件"),
    (16, "H6", "C→A,B", "统一图表 + 汇总表", "A/B 直接引用，不再自己画"),
    (19, "H7", "A,B→C", "Part 1/2/3 草稿", "每节有数字、有图、有来源标注"),
]

fig = plt.figure(figsize=(18, 11.2), dpi=140)
ax = fig.add_axes([0.10, 0.44, 0.86, 0.48])

xmax = 26
for off, *_ in HANDOFFS:
    ax.axvline(off, color="#C0392B", ls=(0, (4, 3)), lw=1.1, alpha=0.55, zorder=0)
ax.axvline(21, color="#333333", lw=2.2, alpha=0.85, zorder=1)
ax.axvline(26, color="#333333", lw=2.2, alpha=0.85, zorder=1)

for name, color, y, tasks in PEOPLE:
    ax.text(-0.9, y + 0.02, name, ha="right", va="center", fontsize=12.5, fontweight="bold")
    for text, s, e in tasks:
        ax.barh(y, width=e - s, left=s, height=0.62, color=color,
                edgecolor="white", linewidth=1.4, zorder=3)
        ax.text(s + (e - s) / 2, y, text, ha="center", va="center",
                fontsize=9.0, color="white", zorder=4)

for i, (off, hid, *_rest) in enumerate(HANDOFFS):
    yy = 2.72 if i % 2 == 0 else 2.98
    ax.plot([off], [yy], marker="o", ms=11, color="#C0392B", zorder=5, clip_on=False)
    ax.text(off, yy - 0.005, hid, ha="center", va="center", fontsize=7.2,
            color="white", fontweight="bold", zorder=6)

ax.set_ylim(-0.65, 3.2)
ax.set_xlim(-0.6, xmax + 0.6)
ticks = list(range(0, 27, 2))
ax.set_xticks(ticks)
ax.set_xticklabels([label(t) for t in ticks], fontsize=9)
ax.set_yticks([])
for side in ("top", "right", "left"):
    ax.spines[side].set_visible(False)
ax.spines["bottom"].set_color("#999999")
ax.tick_params(axis="x", colors="#444444", length=3)
ax.grid(axis="x", color="#E8E8E8", lw=0.6, zorder=0)

ax.text(21, -0.98, "11-25  数字冻结", ha="center", va="top", fontsize=10.5, fontweight="bold")
ax.text(26, -0.98, "11-30  提交", ha="center", va="top", fontsize=10.5, fontweight="bold")
ax.text(0.0, 3.62, "Project 1 工作安排 · 3 人 / 26 天 · 红色虚线 = 交接点",
        ha="left", va="bottom", fontsize=15, fontweight="bold")

axt = fig.add_axes([0.03, 0.02, 0.95, 0.33])
axt.axis("off")
axt.text(0.0, 0.99, "交接清单：交什么、什么时候交、怎么算交成功", fontsize=12.5,
         fontweight="bold", va="top")

colx = [0.0, 0.045, 0.115, 0.215, 0.66]
headers = ["编号", "日期", "方向", "交接物", "验收标准（对方能独立继续）"]
for x, h in zip(colx, headers, strict=True):
    axt.text(x, 0.87, h, fontsize=9.5, fontweight="bold", va="top")
axt.plot([0.0, 0.99], [0.845, 0.845], color="#999999", lw=0.8)

for i, (off, hid, direction, item, accept) in enumerate(HANDOFFS):
    y = 0.79 - i * 0.108
    axt.text(colx[0], y, hid, fontsize=9, fontweight="bold", color="#C0392B", va="top")
    axt.text(colx[1], y, label(off), fontsize=9, va="top")
    axt.text(colx[2], y, direction, fontsize=9, va="top")
    axt.text(colx[3], y, item, fontsize=9, va="top")
    axt.text(colx[4], y, accept, fontsize=9, va="top")
    axt.plot([0.0, 0.99], [y - 0.046, y - 0.046], color="#E6E6E6", lw=0.6)

axt.text(0.0, 0.03,
         "原则：交接物必须是对方能直接用的东西（脚本 / 文件 / 接口），不是口头说明；接不上就算没交接。",
         fontsize=9.5, color="#7B241C", va="bottom")

fig.savefig("docs/workplan.png", bbox_inches="tight", facecolor="white")
print("saved docs/workplan.png")
