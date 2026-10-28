"""环境自检：python check.py  —— 全部 [OK] 再开始实验。"""
import os
import sys

import llm  # 顺带读取 .env

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ok = sys.version_info >= (3, 8)
print(("[OK]  " if ok else "[XX]  ") + f"Python {sys.version.split()[0]}" + ("" if ok else "（需要 3.8 或更高）"))
for k in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"):
    v = bool(os.environ.get(k))
    print(("[OK]  " if v else "[XX]  ") + f"配置了 {k}")
    ok &= v
if ok:
    import loop
    t = loop.TRAIN[1]
    r = loop.decide(loop.SKILL0, t)
    print(f"[OK]  模型可用：作业 {t['id']}（{t['kind']}）Agent 判「{r['decision']}」，细则答案「{t['label']}」，自报把握 {r['confidence']:.0f}%")
print("\n全部通过，可以开始。" if ok else "\n有未通过的项：复制 .env.example 为 .env，填好网关和 key 后重跑（见 README 第 0 步）。")
