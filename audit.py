"""对账：把某次运行里每一轮的候选技能文档（不管被采纳还是被拒绝）拿到训练集和锚集上，用评分细则算真实准确率。

  python audit.py runs/<某次运行>.json

用途：d=1 时评审标准每轮都在变，"采纳/拒绝"已经不可信。对账告诉你被拒绝的到底是好改动还是坏改动。
"""
import json
import sys

import loop

if len(sys.argv) != 2:
    raise SystemExit(__doc__)
d = json.load(open(sys.argv[1], encoding="utf-8"))
base_tr = loop.acc(loop.TRAIN, loop.run_all(loop.SKILL0, loop.TRAIN))
base_an = loop.acc(loop.ANCHOR, loop.run_all(loop.SKILL0, loop.ANCHOR))
print(f"起点技能文档：训练真实 {base_tr:.0%}  锚集真实 {base_an:.0%}\n")
print("轮  循环的决定  训练真实  锚集真实  文档字数  评审标准字数")
for i, r in enumerate(d["rounds"], 1):
    tr = loop.acc(loop.TRAIN, loop.run_all(r["skill"], loop.TRAIN))
    an = loop.acc(loop.ANCHOR, loop.run_all(r["skill"], loop.ANCHOR))
    print(f"{i:<4}{'采纳' if r['accepted'] else '拒绝':<8}{tr:>8.0%}{an:>10.0%}{len(r['skill']):>10}{len(r.get('rubric', '')):>12}")
print(f"\n调用模型 {loop.llm.CALLS['n']} 次")
