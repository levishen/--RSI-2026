"""《数据结构与算法》课程作业评分细则（虚构）。这是"真值"：用代码写死的规则，对每份作业给出唯一正确的结论。

阅卷 Agent 看不到这份代码。它只拿到一份含糊的技能文档，要靠反馈自己把细则学出来。
四种结论：满分 / 扣分 / 零分 / 转人工

按顺序判断，先命中先返回：
 1. 没有附件（attachment 为空）                       → 零分
 2. 查重相似度 ≥ 50%                                   → 转人工（疑似抄袭要人来核实，不能直接判零分）
 3. 迟交超过 72 小时且没有请假条                        → 零分
 4. 按题型给基础结论：
    编程题：测试全部通过 → 满分；通过率 ≥ 60% → 扣分；否则 → 零分
    计算题：答案对且有过程 → 满分；答案对没过程 → 扣分；答案错但有过程 → 扣分（给过程分）；都没有 → 零分
    实验报告：字数 ≥ 800 → 满分；否则 → 扣分
    论述题：字数 < 300 → 零分；字数 ≥ 1500 且引用 ≥ 3 篇 → 满分；其余 → 扣分
 5. 迟交 72 小时以内且没有请假条：基础结论是满分的，降为扣分（有请假条的迟交不扣分）
"""
import json
import random
from pathlib import Path

LABELS = ["满分", "扣分", "零分", "转人工"]


def label(h):
    if not h.get("attachment"):
        return "零分"
    if h["similarity_pct"] >= 50:
        return "转人工"
    late = h["late_hours"] > 0 and not h.get("leave")
    if late and h["late_hours"] > 72:
        return "零分"
    k = h["kind"]
    if k == "编程题":
        r = h["tests_passed"] / h["tests_total"]
        base = "满分" if r == 1 else ("扣分" if r >= 0.6 else "零分")
    elif k == "计算题":
        if h["answer_correct"]:
            base = "满分" if h["has_steps"] else "扣分"
        else:
            base = "扣分" if h["has_steps"] else "零分"
    elif k == "实验报告":
        base = "满分" if h["words"] >= 800 else "扣分"
    elif k == "论述题":
        if h["words"] < 300:
            base = "零分"
        else:
            base = "满分" if h["words"] >= 1500 and h["refs"] >= 3 else "扣分"
    else:
        raise ValueError(k)
    if late and base == "满分":
        return "扣分"
    return base


def _hw(rng, i):
    k = rng.choice(["编程题", "计算题", "实验报告", "论述题"])
    h = {"id": f"H{i:03d}", "kind": k, "attachment": rng.random() > 0.1,
         "similarity_pct": rng.choice([3, 8, 12, 18, 25, 35, 45, 52, 68]) if rng.random() < 0.35 else rng.randint(0, 15),
         "late_hours": 0 if rng.random() < 0.6 else rng.choice([2, 10, 30, 60, 70, 80, 100]),
         "leave": rng.random() < 0.25}
    if k == "编程题":
        h["tests_total"] = rng.choice([10, 20])
        h["tests_passed"] = h["tests_total"] if rng.random() < 0.4 else rng.randint(int(h["tests_total"] * 0.3), h["tests_total"] - 1)
    elif k == "计算题":
        h["answer_correct"] = rng.random() < 0.55
        h["has_steps"] = rng.random() < 0.6
    elif k == "实验报告":
        h["words"] = rng.choice([450, 620, 780, 820, 950, 1300, 2100])
    else:
        h["words"] = rng.choice([180, 260, 700, 1200, 1480, 1550, 2000, 2600])
        h["refs"] = rng.choice([0, 1, 2, 3, 4, 6])
    if not h["attachment"]:
        h["attachment"] = None  # 字段缺失：特征稀疏
    return h


def make(n, seed, start):
    rng = random.Random(seed)
    out = []
    for i in range(n):
        h = _hw(rng, start + i)
        h["label"] = label(h)
        out.append(h)
    return out


def public(h):
    """给 Agent 看的作业：去掉标准答案。"""
    return {k: v for k, v in h.items() if k != "label"}


TRAIN_SEED, ANCHOR_SEED = 206, 1054

if __name__ == "__main__":
    from collections import Counter
    d = Path(__file__).parent / "data"
    d.mkdir(exist_ok=True)
    train, anchor = make(36, TRAIN_SEED, 1), make(40, ANCHOR_SEED, 101)
    for name, rows in (("train", train), ("anchor", anchor)):
        (d / f"{name}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        print(name, len(rows), dict(Counter(h["label"] for h in rows)), dict(Counter(h["kind"] for h in rows)))
