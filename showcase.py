"""生成小组展示页：把组员的运行记录汇总成一页可以投屏的网页。

用法（组长电脑上）：
  1. 新建文件夹 group/，把每个组员 runs/ 里的 json 都放进去（微信、U 盘都行）
  2. 复制 结论模板.md 为 group/结论.md，填好三段话
  3. python3 showcase.py --group "第 3 组" --dir group
  → 生成 展示_第3组.html，用浏览器打开、全屏投影

页面内容：每次运行一张曲线图（循环看到的分数 vs 真实准确率）、关键数字表、AI 写出的细则节选、小组结论。
"""
import argparse
import glob
import html
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
e = html.escape
NAMES = {"v2": "V2 细则代码打分", "v5": "V5 大模型裁判", "v6": "V6 自评把握"}
RULES = {"fails": "只看失败作业", "ineq": "采纳不等式", "sign": "符号检验"}


def series(d):
    rs = [r for r in d["rounds"] if "anchor_cand" in r]
    if not rs:
        return None
    sig = [rs[0]["sig_cur"]] + [r["signal"] for r in rs]
    tr = [rs[0]["train_cur"]] + [r["train_acc"] for r in rs]
    an = [rs[0]["anchor_cur"]] + [r["anchor_acc"] for r in rs]
    acc = [False] + [r["accepted"] for r in rs]
    return sig, tr, an, acc


def chart(sig, tr, an, acc):
    W, H, L, R, T, B = 420, 220, 40, 14, 14, 30
    n = len(sig) - 1
    X = lambda i: L + i * (W - L - R) / max(1, n)
    Y = lambda v: T + (1 - v) * (H - T - B)
    out = [f'<svg viewBox="0 0 {W} {H}" class="ch" role="img" aria-label="每轮分数曲线">']
    for v in (0, 0.25, 0.5, 0.75, 1):
        out.append(f'<line x1="{L}" y1="{Y(v):.1f}" x2="{W - R}" y2="{Y(v):.1f}" class="grid"/><text x="{L - 6}" y="{Y(v) + 4:.1f}" text-anchor="end" class="ax">{int(v * 100)}</text>')
    for i in range(n + 1):
        out.append(f'<text x="{X(i):.1f}" y="{H - 10}" text-anchor="middle" class="ax">{i}</text>')
        if acc[i]:
            out.append(f'<line x1="{X(i):.1f}" y1="{T}" x2="{X(i):.1f}" y2="{H - B}" class="acc"/>')
    for vals, cls in ((sig, "s"), (tr, "t"), (an, "a")):
        pts = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(vals))
        out.append(f'<polyline points="{pts}" class="ln {cls}"/>')
        out.append("".join(f'<circle cx="{X(i):.1f}" cy="{Y(v):.1f}" r="3" class="pt {cls}"/>' for i, v in enumerate(vals)))
    out.append("</svg>")
    return "".join(out)


def read_notes(path):
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    parts = re.split(r"^##\s*(.+)$", text, flags=re.M)
    out = []
    for i in range(1, len(parts) - 1, 2):
        body = parts[i + 1].strip()
        body = "\n".join(l for l in body.splitlines() if not l.strip().startswith(">")).strip()
        if body:
            out.append((parts[i].strip(), body))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--group", required=True, help="组名，例如 第 3 组")
    ap.add_argument("--dir", default="group", help="放组员 json 和 结论.md 的文件夹")
    a = ap.parse_args()
    folder = Path(a.dir)
    runs = []
    for f in sorted(glob.glob(str(folder / "*.json"))):
        d = json.load(open(f, encoding="utf-8"))
        s = series(d)
        if s:
            runs.append((d, s))
    if not runs:
        raise SystemExit(f"{folder} 里没有运行记录。把组员 runs/ 里的 json 复制进来再试。")

    cards, rows, best = [], [], None
    for d, (sig, tr, an, acc) in runs:
        name = f"{NAMES.get(d['signal'], d['signal'])} + {RULES.get(d['accept'], d['accept'])}" + (" · d = 1" if d.get("d") else "")
        gap = (sig[-1] - sig[0]) - (an[-1] - an[0])
        flag = "循环自以为进步了，真实却没有" if sig[-1] - sig[0] > 0.03 and an[-1] - an[0] <= 0 else ("真实进步" if an[-1] - an[0] >= 0.075 else "变化在噪声内")
        cards.append(f"<div class='run'><h3>{e(name)}</h3>{chart(sig, tr, an, acc)}"
                     f"<p class='cap'>分数 {sig[0]:.2f} → {sig[-1]:.2f} · 锚集 {an[0]:.0%} → {an[-1]:.0%} · <b>{flag}</b>"
                     + ("（V2 的分数就是训练集准确率，橙线和蓝线重合）" if d['signal'] == 'v2' else "") + "</p></div>")
        broke = sum(r.get("broke", 0) for r in d["rounds"])
        rows.append(f"<tr><td>{e(name)}</td><td class='n'>{sum(acc)}</td><td class='n'>{broke}</td><td class='n'>{tr[0]:.0%} → {tr[-1]:.0%}</td>"
                    f"<td class='n'>{an[0]:.0%} → {an[-1]:.0%}</td><td class='n'>{len(d.get('final_skill', ''))}</td></tr>")
        if best is None or an[-1] > best[0]:
            best = (an[-1], name, d.get("final_skill", ""))
    notes = read_notes(folder / "结论.md")
    notes_html = "".join(f"<div class='note'><h4>{e(t)}</h4><p>{e(b)}</p></div>" for t, b in notes) or \
        "<div class='note'><h4>还没填结论</h4><p>复制 结论模板.md 到 group/结论.md 并填写三段话，再重新运行 showcase.py。</p></div>"
    skill = best[2][:520] + ("……" if len(best[2]) > 520 else "")

    page = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(a.group)} · 阅卷 Agent 实验</title>
<style>
:root{{--bg:#F5F7F6;--card:#fff;--ink:#16232B;--muted:#5B6B72;--rule:#D3DBD9;--acc:#0E7C6B;--warn:#B4561B;--blue:#3D6FA8}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 "PingFang SC","Microsoft YaHei",system-ui,sans-serif}}
.wrap{{max-width:1280px;margin:0 auto;padding:24px 16px 40px}}
h1{{font-size:34px;margin:0}} .sub{{color:var(--muted);margin:4px 0 18px}}
.runs{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}}
.run,.note,table{{background:var(--card);border:1px solid var(--rule);border-radius:6px}}
.run{{padding:10px 14px}} .run h3{{font-size:16px;margin:2px 0 4px}} .cap{{font-size:13px;color:var(--muted);margin:2px 0}}
.ch{{width:100%;height:auto}} .grid{{stroke:var(--rule)}} .ax{{font-size:10px;fill:var(--muted)}} .acc{{stroke:var(--acc);stroke-dasharray:3 3;opacity:.5}}
.ln{{fill:none;stroke-width:2.5}} .ln.s{{stroke:var(--warn)}} .ln.t{{stroke:var(--blue)}} .ln.a{{stroke:var(--acc)}}
.pt.s{{fill:var(--warn)}} .pt.t{{fill:var(--blue)}} .pt.a{{fill:var(--acc)}}
.legend{{font-size:13px;color:var(--muted);margin:8px 0 18px}} .legend b{{display:inline-block;width:14px;height:4px;vertical-align:middle;margin:0 4px 0 12px}}
.cols{{display:grid;grid-template-columns:1.1fr 1fr;gap:16px;margin-top:18px}} @media (max-width:800px){{.cols{{grid-template-columns:1fr}}}}
table{{border-collapse:collapse;width:100%;font-size:14px}} th,td{{text-align:left;padding:7px 10px;border-bottom:1px solid var(--rule)}} th{{color:var(--muted);font-size:12.5px}} td.n{{font-variant-numeric:tabular-nums;white-space:nowrap}}
pre{{background:var(--card);border:1px solid var(--rule);border-radius:6px;padding:12px;white-space:pre-wrap;font-size:13px;line-height:1.55;max-height:300px;overflow:auto;margin:0}}
.notes{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-top:18px}} @media (max-width:800px){{.notes{{grid-template-columns:1fr}}}}
.note{{padding:12px 16px;border-top:4px solid var(--acc)}} .note h4{{margin:0 0 6px;font-size:15px;color:var(--acc)}} .note p{{margin:0;font-size:17px;white-space:pre-wrap}}
h2{{font-size:18px;margin:0 0 8px}}
</style></head><body><div class="wrap">
<h1>{e(a.group)}：我们让阅卷 Agent 改了自己</h1>
<p class="sub">{len(runs)} 次运行 · 起点：训练集 {runs[0][1][1][0]:.0%}，锚集 {runs[0][1][2][0]:.0%}（锚集 40 份作业从不参与决定，只用来对账）</p>
<div class="legend">图例：<b style="background:var(--warn)"></b>循环看到的分数<b style="background:var(--blue)"></b>训练集真实准确率<b style="background:var(--acc)"></b>锚集真实准确率　虚线 = 这一轮的改动被采纳　横轴 = 第几轮</div>
<div class="runs">{''.join(cards)}</div>
<div class="notes">{notes_html}</div>
<div class="cols">
  <div style="min-width:0"><h2>关键数字</h2><div style="overflow-x:auto"><table><tr><th>配置</th><th>采纳</th><th>改坏（份）</th><th>训练集</th><th>锚集</th><th>文档字数</th></tr>{''.join(rows)}</table></div></div>
  <div style="min-width:0"><h2>锚集最高的那次，AI 写出的细则（节选）</h2><pre>{e(skill)}</pre></div>
</div>
</div></body></html>"""
    out = Path(f"展示_{re.sub(r'[^0-9A-Za-z一-龥]', '', a.group)}.html")
    out.write_text(page, encoding="utf-8")
    print(f"已生成 {out}，用浏览器打开后全屏投影。")


if __name__ == "__main__":
    main()
