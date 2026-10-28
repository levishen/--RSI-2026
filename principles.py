"""追问对账：用你们自己跑出来的数据，检验讲授里的五个追问。

  python principles.py <runs 文件夹，默认 runs>

每一轮的候选（不论被采纳还是拒绝）都在锚集上测过真实准确率，这里把"循环看到的"和"真实发生的"放在一起比。
样本小的地方都打印了 n 和区间：区间很宽时，结论就是"还看不清"。全班的 json 放进同一个文件夹再跑，区间会变窄。
"""
import glob
import json
import math
import statistics
import sys
from collections import defaultdict

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

folder = sys.argv[1] if len(sys.argv) > 1 else "runs"
rows = []
for f in glob.glob(f"{folder}/*.json"):
    d = json.load(open(f, encoding="utf-8"))
    for r in d["rounds"]:
        if "anchor_cand" in r:  # 只用带对账字段的新记录
            rows.append({**r, "signal_kind": d["signal"], "rule": d["accept"], "d": d["d"]})
if not rows:
    raise SystemExit(f"{folder} 里没有带对账字段的运行记录。先用 loop.py 跑几次。")
N_ANCHOR = 40
GOOD = 3  # 候选在锚集上比当前版本至少多对 3 份，才算"真好"（多对 1 份很容易是噪声）


def corr(xs, ys):
    if len(xs) < 4 or statistics.pstdev(xs) == 0 or statistics.pstdev(ys) == 0:
        return float("nan"), (float("nan"), float("nan"))
    mx, my = statistics.mean(xs), statistics.mean(ys)
    r = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / math.sqrt(
        sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
    z, se = math.atanh(max(-0.999999, min(0.999999, r))), 1 / math.sqrt(len(xs) - 3)  # Fisher 变换的 95% 区间
    return r, (math.tanh(z - 1.96 * se), math.tanh(z + 1.96 * se))


def sign_p(b, c):
    n = b + c
    return sum(math.comb(n, k) for k in range(b, n + 1)) / 2 ** n if n else 1.0


def frac(k, n):
    return f"{k}/{n}" if n else "—"


print(f"共 {len(rows)} 个候选（来自 {folder}）。同一次运行里的候选并不独立，下面的区间只能偏乐观地看。\n")

print("━━ 追问 1 · 分数可信吗：代理信号和真实质量的相关 ρ ━━")
print("这里的 ρ 用变化量估计：候选相对当前版本，循环看到的分数变了多少 vs 锚集真实准确率变了多少。")
print("锚集本身有测量噪声，会把 ρ 往 0 压（衰减效应）。")
for k in ("v2", "v5", "v6"):
    g = [r for r in rows if r["signal_kind"] == k]
    if g:
        rho, (lo, hi) = corr([r["sig_cand"] - r["sig_cur"] for r in g], [r["anchor_cand"] - r["anchor_cur"] for r in g])
        print(f"  {k}：ρ = {rho:+.2f}，95% 区间 [{lo:+.2f}, {hi:+.2f}]，n = {len(g)}")

print("\n━━ 追问 2 · 用分数挑会被骗吗：训练集涨幅 − 锚集涨幅 ━━")
print("被采纳的候选：训练集看起来涨了多少，锚集实际涨了多少。两者之差混着三样东西：")
print("选择偏差（赢家诅咒 / 失败作业回归均值）、对看过答案的训练作业的拟合、训练集与锚集的分布差。")
for rule in ("fails", "ineq", "sign"):
    g = [r for r in rows if r["rule"] == rule and r["accepted"] and r["signal_kind"] == "v2"]
    if len(g) >= 2:
        diffs = [(r["train_cand"] - r["train_cur"]) - (r["anchor_cand"] - r["anchor_cur"]) for r in g]
        se = statistics.stdev(diffs) / math.sqrt(len(diffs))
        print(f"  v2 + {rule:<5}：采纳 {len(g)} 次，训练集平均 {statistics.mean(r['train_cand'] - r['train_cur'] for r in g):+.1%}，"
              f"锚集平均 {statistics.mean(r['anchor_cand'] - r['anchor_cur'] for r in g):+.1%}，差 {statistics.mean(diffs):+.1%} ± {se:.1%}（标准误）")
    elif g:
        print(f"  v2 + {rule:<5}：只采纳 {len(g)} 次，样本太少")

print("\n━━ 追问 3 · 这次改动真的变好了吗：修好 b 份、改坏 c 份 ━━")
print("精确单侧符号检验：候选其实没变好时，出现 ≥ b 份变好的概率 p。p < 0.05 才算显著。")
for rule in ("fails", "ineq", "sign"):
    g = [r for r in rows if r["rule"] == rule and r["accepted"] and r["signal_kind"] == "v2"]
    if g:
        ps = [sign_p(r["fixed"], r["broke_all"]) for r in g]
        flat = sum(r["fixed"] <= r["broke_all"] for r in g)
        print(f"  v2 + {rule:<5}：采纳 {len(g)} 次，其中 p ≥ 0.05 的 {sum(p >= 0.05 for p in ps)} 次，"
              f"修好 ≤ 改坏（训练集持平或变差）的 {flat} 次")
    else:
        print(f"  v2 + {rule:<5}：一次都没采纳")
print("  注意：同一份训练集每轮检验一次，5 轮下来总的误放率接近 1 − 0.95⁵ ≈ 23%。")

print(f"\n━━ 追问 4 · 留下的改动有多少真好：把采纳规则当成检测器 ━━")
print(f"'真好' = 候选在锚集上比当前版本至少多对 {GOOD} 份。每格样本很少，只能示意；各规则的 p 不同，后验不能横向比。")
by = defaultdict(list)
for r in rows:
    by[f"{r['signal_kind']}+{r['rule']}" + ("+d1" if r["d"] else "")].append(r)
for k in sorted(by):
    g = by[k]
    good = [round((r["anchor_cand"] - r["anchor_cur"]) * N_ANCHOR) >= GOOD for r in g]
    acc_ = [r["accepted"] for r in g]
    ng, nb = sum(good), len(g) - sum(good)
    tp = sum(a and gd for a, gd in zip(acc_, good))
    fp = sum(a and not gd for a, gd in zip(acc_, good))
    print(f"  {k:<14} 候选 {len(g):>2}  真好 {frac(ng, len(g)):>5}  TPR {frac(tp, ng):>5}  FPR {frac(fp, nb):>5}  "
          f"被采纳的里真好 {frac(tp, tp + fp):>5}")

print("\n━━ 追问 5 · 样本够吗：锚集能分辨多大的差别 ━━")
flips = [abs(r["anchor_cand"] - r["anchor_cur"]) for r in rows]
print("两个版本在同一个 40 份的锚集上比，是配对比较：只有结论不同的作业带信息。")
for m in (6, 12, 18):
    need = next(b for b in range(m + 1) if sign_p(b, m - b) < 0.05)
    print(f"  若两版有 {m:>2} 份结论不同：要 {need} 份变好、{m - need} 份变差（净多对 {2 * need - m} 份 = {(2 * need - m) / N_ANCHOR:.1%}）才显著")
print(f"  单个版本准确率的标准误：p = 75% 时 {math.sqrt(0.75 * 0.25 / N_ANCHOR):.1%}；想减半，锚集要扩大到 4 倍（标准误 ∝ 1/√n）。")
