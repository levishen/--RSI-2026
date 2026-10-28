"""全班汇总：把大家 runs/ 目录里的 json 放到同一个文件夹，按配置统计最终结果。

  python summarize.py <文件夹，默认 runs>

一次运行只是 E0/E1 级证据；同一配置有多次独立运行、并且看锚集，才接近 E2。
"""
import glob
import json
import statistics
import sys
from collections import defaultdict

folder = sys.argv[1] if len(sys.argv) > 1 else "runs"
groups = defaultdict(list)
for f in glob.glob(f"{folder}/*.json"):
    d = json.load(open(f, encoding="utf-8"))
    rs = d["rounds"]
    last = rs[-1] if rs else {}
    groups[f"{d['signal']}-{d['accept']}-d{d['d']}"].append({
        "train": last.get("train_acc", 0), "anchor": last.get("anchor_acc", 0),
        "broke": sum(r["broke"] for r in rs), "accepted": sum(r["accepted"] for r in rs),
        "len": len(d.get("final_skill", ""))})


def ms(xs, pct=True):
    """均值 ± 标准误（SD/√k）。运行次数 k 越多，标准误越小，这正是原理六。"""
    m = statistics.mean(xs)
    se = statistics.stdev(xs) / len(xs) ** 0.5 if len(xs) > 1 else 0
    return f"{m:.0%}±{se:.0%}" if pct else f"{m:.1f}±{se:.1f}"


print(f"{'配置':<16}{'次数':>4}{'训练真实':>12}{'锚集真实':>12}{'训练-锚集(水平差)':>12}{'改坏(份)':>12}{'采纳轮数':>10}{'文档字数':>12}")
for k in sorted(groups):
    g = groups[k]
    gap = statistics.mean(x["train"] - x["anchor"] for x in g)
    print(f"{k:<16}{len(g):>4}{ms([x['train'] for x in g]):>13}{ms([x['anchor'] for x in g]):>12}{gap:>+10.0%}"
          f"{ms([x['broke'] for x in g], False):>13}{ms([x['accepted'] for x in g], False):>10}{ms([x['len'] for x in g], False):>13}")
print("\n± 是标准误（各次运行的标准差 / √次数），次数越多越小。起点：训练真实 42%，锚集真实 60%")
