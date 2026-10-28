"""最小 LLM 客户端：只用标准库，兼容任何 OpenAI 格式接口。

配置：LLM_BASE_URL（以 /v1 结尾）、LLM_API_KEY、LLM_MODEL、LLM_WORKERS。
可以写在仓库根目录的 .env 里（复制 .env.example），也可以设成环境变量；环境变量优先。
"""
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def load_dotenv(path=Path(__file__).parent / ".env"):
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_dotenv()

BASE_URL = os.environ.get("LLM_BASE_URL", "").rstrip("/")
API_KEY = os.environ.get("LLM_API_KEY", "")
MODEL = os.environ.get("LLM_MODEL", "claude-sonnet-4-6")
CALLS = {"n": 0}
_lock = threading.Lock()


def chat(messages, temperature=0.0, max_tokens=600):
    if not (BASE_URL and API_KEY):
        raise SystemExit("请先在 .env 里填好 LLM_BASE_URL 和 LLM_API_KEY（见 README 第 0 步）。")
    with _lock:
        CALLS["n"] += 1
    body = json.dumps({"model": MODEL, "messages": messages, "temperature": temperature,
                       "max_tokens": max_tokens}).encode()
    req = urllib.request.Request(BASE_URL + "/chat/completions", data=body, headers={
        "Content-Type": "application/json", "Authorization": "Bearer " + API_KEY})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read())["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 529) and attempt < 4:
                time.sleep(2 ** attempt * 2)
                continue
            raise SystemExit(f"接口报错 {e.code}：{e.read().decode(errors='ignore')[:200]}")
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < 4:
                time.sleep(2 ** attempt * 2)
                continue
            raise SystemExit(f"网络错误：{e}")


WORKERS = int(os.environ.get("LLM_WORKERS", "8"))  # 全班同时跑时调小，例如 4


def pmap(fn, items, workers=None):
    with ThreadPoolExecutor(max_workers=workers or WORKERS) as ex:
        return list(ex.map(fn, items))


def parse_json(text):
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}


if hasattr(sys.stdout, "reconfigure"):  # Windows 中文控制台
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
