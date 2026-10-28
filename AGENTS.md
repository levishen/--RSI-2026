# AGENTS.md · 给 AI 编程助手的说明

你在帮一位学生做《递归之桥》课程的实践：跑一个最小的递归自我改进（RSI）循环，让阅卷 Agent 改写自己的技能文档，再用五个追问检验"进步"是不是真的。完整手册见 [README.md](README.md)，学生会按里面的步骤编号（0–5）向你提要求。

## 环境

- 只需要 Python 3.8+，**不要 pip install 任何东西**，所有脚本只用标准库。
- 配置在仓库根目录的 `.env`（从 `.env.example` 复制）：`LLM_BASE_URL`（以 `/v1` 结尾）、`LLM_API_KEY`、`LLM_MODEL`、`LLM_WORKERS`。脚本启动时自动读取，不需要 export。
- macOS / Linux 用 `python3`；Windows 用 `python`，中文乱码先 `chcp 65001`。

## 常用命令

| 学生说 | 你执行 |
|---|---|
| 第 0 步 / 配环境 | `cp .env.example .env`，把学生给的网关和 key 填进 `.env`，再跑 `python3 check.py`，把输出原样给学生 |
| 实验一 A / B / C / D | `python3 loop.py --signal v2 --accept fails` / `--signal v2 --accept ineq` / `--signal v2 --accept sign` / `--signal v6 --accept ineq` |
| 实验二 | `python3 loop.py --signal v5 --accept ineq --d 1`，跑完 `python3 audit.py runs/<刚生成的 json>` |
| 看汇总 | `python3 summarize.py runs` |
| 做展示页 | 把组员的 json 放进 `group/`，按 `结论模板.md` 写 `group/结论.md`，再 `python3 showcase.py --group "第 N 组" --dir group` |
| 接口坏了 / 来不及 | 用 `rehearsal_outputs/` 里的 json 代替 `runs/` 的，命令不变 |

`loop.py` 一次运行约 6–13 分钟、几百次模型调用。**放在前台跑，把每轮输出的表格原样给学生看**，不要只汇报最后结果，表格本身就是教学内容。

## 规则

1. **不要修改** `policy.py`、`data/`、`loop.py`、`llm.py`、`rehearsal_outputs/`：它们是实验的真值和对照组。学生明确要做"课后挑战"时才可以改，并先说明会改哪里。
2. **不要把 key 打印出来、写进 `.env` 以外的文件，或提交到 git。**
3. 不要替学生写结论。`group/结论.md` 的三段话由学生自己写；你可以帮着找数字、解释某一列是什么意思。
4. 解释结果时，先问"样本够不够"：一次运行的数字有随机性，和 README 里的彩排结果不同是正常的。
5. 报错先查 README 的"故障处理"表；`429` 或很慢就把 `.env` 里的 `LLM_WORKERS` 调到 2。
