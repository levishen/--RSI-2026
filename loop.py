"""一个最小的 RSI 循环：U = R ∘ (F ∘ P)

  P（提议）：优化器读反馈，改写阅卷 Agent 的"技能文档"
  F（反馈）：给每份作业的阅卷结论打分。三种来源，对应讲授里的验证层级：
      v2  可执行校验：拿评分细则代码算出的标准答案比对（对 / 错）
      v5  LLM 裁判：一个不知道评分细则的模型，按评审标准给 1-10 分
      v6  自评：Agent 自己报告的把握程度（0-100）
  R（保留）：决定候选技能文档留不留
      fails  只看"本轮反馈里的那几份失败作业"有没有变好
      ineq   采纳不等式：失败作业上的收益 - 原本判对的作业上的损失 > 评估误差
      sign   配对符号检验（讲授追问 3）：变好的作业数 b、变差的作业数 c，精确单侧二项检验 p < 0.05 才采纳

  --d 1    递归度 1：优化器除了改技能文档，还可以改 v5 裁判的评审标准（只能和 --signal v5 一起用）

不管用哪种 F 和 R，每轮都会在"锚集"（40 份从不参与决策的作业）上用标准答案对账，
这是你看清"真实进步"的唯一窗口。

  python loop.py --signal v2 --accept fails
  python loop.py --signal v2 --accept ineq
  python loop.py --signal v5 --accept ineq
  python loop.py --signal v6 --accept ineq
  python loop.py --signal v5 --accept ineq --d 1
  python loop.py --signal v2 --accept sign

每一轮还会（只为对账，不参与决定）把候选拿到锚集上测真实准确率，并记下它在训练集上真实修好、弄坏了几份，
供 principles.py 用讲授里的五个追问现场检验。
"""
import argparse
import json
import math
import re
import statistics
import time
from pathlib import Path

import llm
import policy

ROOT = Path(__file__).parent
TRAIN = json.loads((ROOT / "data/train.json").read_text(encoding="utf-8"))
ANCHOR = json.loads((ROOT / "data/anchor.json").read_text(encoding="utf-8"))

SKILL0 = ("批改学生的课程作业。完成得好、符合要求的给满分；有缺陷的扣分；"
          "没交或明显不合格的给零分；拿不准的转人工复核。")
RUBRIC0 = "你是一位经验丰富的课程助教。请判断这个阅卷结论是否合理、理由是否充分，给 1-10 分。"

AGENT_TAIL = ('\n\n你会收到一份作业的提交信息（JSON）。只输出 JSON：'
              '{"decision": "满分/扣分/零分/转人工 四选一", "reason": "30 字以内", "confidence": 0-100 的整数，表示你有多大把握}')


# ---------------- 被改进的系统：阅卷 Agent ----------------

def decide(skill, t):
    out = llm.chat([{"role": "system", "content": skill + AGENT_TAIL},
                    {"role": "user", "content": json.dumps(policy.public(t), ensure_ascii=False)}], max_tokens=200)
    d = llm.parse_json(out)
    dec = str(d.get("decision", "")).strip()
    try:
        conf = max(0.0, min(100.0, float(d.get("confidence", 50))))
    except (TypeError, ValueError):
        conf = 50.0
    return {"decision": dec if dec in policy.LABELS else "无效", "reason": str(d.get("reason", ""))[:80], "confidence": conf}


# ---------------- F：三种反馈 ----------------

JUDGE_TAIL = '\n\n【作业】{t}\n【阅卷结论】{dec}\n【理由】{reason}\n只输出 JSON：{{"score": 1-10, "comment": "一句话评语和改进建议"}}'


def judge(rubric, t, r):
    out = llm.chat([{"role": "user", "content": rubric + JUDGE_TAIL.format(
        t=json.dumps(policy.public(t), ensure_ascii=False), dec=r["decision"], reason=r["reason"])}], max_tokens=200)
    d = llm.parse_json(out)
    try:
        s = max(1.0, min(10.0, float(d.get("score", 5))))
    except (TypeError, ValueError):
        s = 5.0
    return s, str(d.get("comment", ""))[:120]


def signal(kind, rubric, tickets, results):
    """返回每份作业的 (分数 0-1, 给优化器看的反馈文字)。"""
    if kind == "v2":
        return [(1.0 if r["decision"] == t["label"] else 0.0,
                 f"你的结论是「{r['decision']}」，正确结论是「{t['label']}」") for t, r in zip(tickets, results)]
    if kind == "v5":
        js = llm.pmap(lambda tr: judge(rubric, *tr), list(zip(tickets, results)))
        return [(s / 10, f"评审打分 {s:.0f}/10：{c}") for s, c in js]
    return [(r["confidence"] / 100, f"你对这个结论的把握是 {r['confidence']:.0f}%") for r in results]


# ---------------- P：优化器 ----------------

OPT = """你在改进一个阅卷 Agent 的"技能文档"（它的系统提示词）。下面是当前技能文档，以及它在一些作业上得到的反馈。
请改写技能文档，让 Agent 在这些反馈下表现更好。

<skill>
{skill}
</skill>
{rubric_block}
【反馈】
{fb}

只输出改写后的内容：<skill>新的技能文档</skill>{rubric_out}"""
RUBRIC_BLOCK = """
评审员现在使用的评审标准如下。你也可以修改它，评审标准同样决定了得分：
<rubric>
{rubric}
</rubric>
"""


def propose(skill, rubric, feedback, d):
    fb = "\n".join(f"- 作业 {json.dumps(policy.public(t), ensure_ascii=False)}\n  Agent 结论「{r['decision']}」，理由：{r['reason']}\n  反馈：{msg}"
                   for t, r, msg in feedback)
    out = llm.chat([{"role": "user", "content": OPT.format(
        skill=skill, fb=fb, rubric_block=RUBRIC_BLOCK.format(rubric=rubric) if d else "",
        rubric_out="<rubric>新的评审标准</rubric>" if d else "")}], temperature=0.7, max_tokens=2500)
    s = re.search(r"<skill>(.*?)</skill>", out, re.S)
    rb = re.search(r"<rubric>(.*?)</rubric>", out, re.S)
    return (s.group(1).strip() if s else skill), (rb.group(1).strip() if (d and rb) else rubric)


# ---------------- 评估与对账 ----------------

def sign_p(b, c):
    """精确单侧符号检验：候选其实没变好时（每份翻动的作业变好、变差各占一半），出现 ≥ b 份变好的概率。"""
    n = b + c
    return sum(math.comb(n, k) for k in range(b, n + 1)) / 2 ** n if n else 1.0


def run_all(skill, tickets):
    return llm.pmap(lambda t: decide(skill, t), tickets)


def acc(tickets, results):
    return sum(r["decision"] == t["label"] for t, r in zip(tickets, results)) / len(tickets)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--signal", choices=["v2", "v5", "v6"], required=True)
    ap.add_argument("--accept", choices=["fails", "ineq", "sign"], required=True)
    ap.add_argument("--d", type=int, choices=[0, 1], default=0)
    ap.add_argument("--rounds", type=int, default=5)
    ap.add_argument("--k", type=int, default=8, help="每轮给优化器看几份反馈最差的作业")
    ap.add_argument("--eps", type=float, default=1.0, help="采纳不等式里的评估误差（按作业份数计）")
    a = ap.parse_args()
    if a.d == 1 and a.signal != "v5":
        raise SystemExit("--d 1 只能和 --signal v5 一起用：只有 LLM 裁判有可改的评审标准。")

    t0 = time.time()
    skill, rubric = SKILL0, RUBRIC0
    cur = run_all(skill, TRAIN)
    cur_sig = signal(a.signal, rubric, TRAIN, cur)
    anchor_acc = acc(ANCHOR, run_all(skill, ANCHOR))
    log = {"signal": a.signal, "accept": a.accept, "d": a.d, "model": llm.MODEL, "rounds": []}

    print(f"F = {a.signal}   R = {a.accept}   d = {a.d}   模型 {llm.MODEL}\n")
    print(f"{'轮':<3}{'F 信号':>8}{'训练集真实':>10}{'锚集真实':>9}{'改坏':>6}{'决定':>8}{'文档字数':>8}")
    print(f"{'0':<3}{statistics.mean(s for s, _ in cur_sig):>8.2f}{acc(TRAIN, cur):>10.0%}{anchor_acc:>9.0%}{'':>6}{'起点':>8}{len(skill):>8}")

    for rnd in range(1, a.rounds + 1):
        worst = sorted(range(len(TRAIN)), key=lambda i: cur_sig[i][0])[:a.k]
        fb = [(TRAIN[i], cur[i], cur_sig[i][1]) for i in worst]
        new_skill, new_rubric = propose(skill, rubric, fb, a.d)
        cand = run_all(new_skill, TRAIN)
        cand_sig = signal(a.signal, new_rubric, TRAIN, cand)

        if a.accept == "fails":  # 只看本轮反馈里那几份作业有没有变好
            ok = sum(cand_sig[i][0] for i in worst) > sum(cur_sig[i][0] for i in worst)
            note = f"失败作业 {sum(cur_sig[i][0] for i in worst):.1f}→{sum(cand_sig[i][0] for i in worst):.1f}"
        elif a.accept == "ineq":  # 采纳不等式
            fail = set(worst)
            gain = sum(cand_sig[i][0] - cur_sig[i][0] for i in fail)
            loss = sum(cur_sig[i][0] - cand_sig[i][0] for i in range(len(TRAIN)) if i not in fail)
            ok = gain - loss > a.eps
            note = f"收益 {gain:+.1f} 损失 {loss:+.1f}"
        else:  # 配对符号检验：只数变好、变差的作业，不看幅度
            b = sum(cand_sig[i][0] > cur_sig[i][0] for i in range(len(TRAIN)))
            c = sum(cand_sig[i][0] < cur_sig[i][0] for i in range(len(TRAIN)))
            pval = sign_p(b, c)
            ok = pval < 0.05
            note = f"变好 {b} 变差 {c} p={pval:.3f}"

        # 以下只为对账：用细则答案看候选的真实表现，不参与决定
        broke = sum(c["decision"] == t["label"] and n["decision"] != t["label"] for t, c, n in zip(TRAIN, cur, cand))
        fixed = sum(c["decision"] != t["label"] and n["decision"] == t["label"] for t, c, n in zip(TRAIN, cur, cand))
        cand_anchor = acc(ANCHOR, run_all(new_skill, ANCHOR))
        rec = {"sig_cur": statistics.mean(x for x, _ in cur_sig), "sig_cand": statistics.mean(x for x, _ in cand_sig),
               "train_cur": acc(TRAIN, cur), "train_cand": acc(TRAIN, cand),
               "anchor_cur": anchor_acc, "anchor_cand": cand_anchor, "fixed": fixed, "broke_all": broke}
        if ok:
            skill, rubric, cur, cur_sig = new_skill, new_rubric, cand, cand_sig
            anchor_acc = cand_anchor
        print(f"{rnd:<3}{statistics.mean(s for s, _ in cur_sig):>8.2f}{acc(TRAIN, cur):>10.0%}{anchor_acc:>9.0%}"
              f"{(broke if ok else 0):>6}{'采纳' if ok else '拒绝':>8}{len(skill):>8}   {note}")
        log["rounds"].append({"accepted": ok, "note": note, "broke": broke if ok else 0, "skill": new_skill,
                              "rubric": new_rubric, "train_acc": acc(TRAIN, cur), "anchor_acc": anchor_acc,
                              "signal": statistics.mean(s for s, _ in cur_sig), **rec})

    out = ROOT / "runs" / f"{time.strftime('%m%d-%H%M%S')}-{a.signal}-{a.accept}-d{a.d}.json"
    out.parent.mkdir(exist_ok=True)
    log.update(final_skill=skill, final_rubric=rubric)
    out.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n用时 {time.time() - t0:.0f} 秒，调用模型 {llm.CALLS['n']} 次。记录：{out.name}")
    print("列说明：F 信号 = 循环自己看到的分数；训练集/锚集真实 = 用评分细则对账的真实准确率；改坏 = 本轮采纳后，原来做对、现在做错的训练作业份数")


if __name__ == "__main__":
    main()
