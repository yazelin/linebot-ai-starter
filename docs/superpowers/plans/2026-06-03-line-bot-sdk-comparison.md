# line-bot-sdk Comparison Second-Half Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a second course track that reimplements the hand-rolled LINE integration (signature / event parsing / Reply API) with the official `line-bot-sdk` v3, sharing the bot reply logic, as a contrast lesson.

**Architecture:** Keep `app/main.py` + `app/line.py` (hand-rolled) unchanged in behavior. Extract the reply-resolution logic into `app/bot.py` (shared). Add `app/line_sdk.py` + `app/main_sdk.py` using line-bot-sdk v3 async, reachable only via an optional `sdk` extra. One parametrized smoke test (`LINEBOT_SMOKE_TARGET`) drives either app through a proper signed webhook against a local fake LINE server and asserts identical replies, proving parity. A Quick Reply bonus shows SDK-only typed rich messages.

**Tech Stack:** Python 3.10+, uv, FastAPI 0.115.6 (existing), line-bot-sdk 3.23.x (optional extra), Starlette TestClient (no pytest), GitHub Actions.

---

## Preconditions / verified facts

All probed against **line-bot-sdk 3.23.0** and the scratch parity harness (both targets passed):

- `Configuration(host=...)` overrides the API base → SDK reply can target a local fake LINE server.
- `AsyncMessagingApi.reply_message(ReplyMessageRequest(reply_token=..., messages=[TextMessage(text=...)]))` POSTs to `<host>/v2/bot/message/reply` with body `{"replyToken":...,"messages":[{"type":"text","text":...}],"notificationDisabled":false}` — same path + shape as the hand-rolled version.
- The fake LINE server must return `{"sentMessages":[{"id":"1","quoteToken":"qt"}]}` or the SDK raises ValidationError parsing the response.
- `WebhookParser(secret).parse(body, signature)`: valid → `MessageEvent` (`ev.message.text`, `ev.reply_token`); invalid → `InvalidSignatureError`.
- The webhook fixture MUST be a complete LINE event — text messages need `quoteToken`, plus `mode`/`timestamp`/`source`/`webhookEventId`/`deliveryContext` — else the SDK parses it as `UnknownEvent` (no `.message`).
- Starlette `TestClient(app)` drives the async webhook in-process; the async outbound call (httpx for hand-rolled, aiohttp for SDK) reaches the threaded local fake server fine. A `StarletteDeprecationWarning` about httpx may print — harmless, ignore.
- `config.py` reads env at import time, so the smoke test sets env BEFORE importing the target module.

**Working dir:** `/home/ct/linebot-ai-starter`. Branch: `feat/line-bot-sdk-comparison-track` (not main).

---

## File structure

| File | Responsibility |
|---|---|
| `app/bot.py` (create) | Shared `resolve_reply(text)` + `KEYWORD_REPLIES` |
| `app/config.py` (modify) | Add `LINE_API_BASE` |
| `app/line.py` (modify) | Use `bot.resolve_reply`; reply via `LINE_API_BASE` |
| `app/line_sdk.py` (create) | SDK signature/parse/reply + Quick Reply bonus |
| `app/main_sdk.py` (create) | FastAPI app wiring the SDK webhook |
| `pyproject.toml` (modify) | `sdk` optional extra |
| `parity_smoke_test.py` (create) | Parametrized parity test (local fake LINE + TestClient) |
| `bonus_smoke_test_sdk.py` (create) | SDK-only Quick Reply check |
| `.github/workflows/ci.yml` (create) | Matrix: handrolled + sdk tracks |
| `docs/08-line-bot-sdk-comparison.md` (create) | The lesson |
| `docs/00-overview.md`, `tutorial.html`, `README.md`, `index.html`, `DESIGN.md` (modify) | Two-track framing |

---

## Task 1: Extract shared bot logic + make reply base URL configurable

**Files:** Create `app/bot.py`; Modify `app/config.py`, `app/line.py`; Create `parity_smoke_test.py`.

- [ ] **Step 1: Add `LINE_API_BASE` to `app/config.py`.** Append after the existing `MODEL_NAME` line:

```python
LINE_API_BASE=os.getenv("LINE_API_BASE","https://api.line.me")
```

- [ ] **Step 2: Create `app/bot.py`** (shared reply logic, moved out of line.py):

```python
"""Shared bot reply logic — used by BOTH the hand-rolled (app/line.py) and the
line-bot-sdk (app/line_sdk.py) implementations, so the two behave identically."""
from .ai import ask_ai

# 關鍵字自動回覆表：訊息文字完全相符時，直接回固定字串，不經過 AI。
KEYWORD_REPLIES = {
    "/ping": "pong",
    "營業時間": "我們的營業時間是週一到週五 09:00-18:00。",
}


async def resolve_reply(text: str) -> str:
    """Resolve an incoming text message to a reply string (keyword table first,
    otherwise the AI provider), truncated to LINE's practical length limit."""
    reply = KEYWORD_REPLIES[text] if text in KEYWORD_REPLIES else await ask_ai(text)
    return reply[:4500]
```

- [ ] **Step 3: Write the parity smoke test (this is the test).** Create `parity_smoke_test.py`:

```python
#!/usr/bin/env python3
"""Parity smoke test for the LINE webhook surface shared by both implementations.

Spins a local fake LINE server, points the target app's Reply API at it via
LINE_API_BASE, drives the app through a proper signed webhook with Starlette's
TestClient, and asserts the captured reply. The SAME assertions pass against
app.main (hand-rolled) and app.main_sdk (line-bot-sdk), proving parity.

Target chosen by LINEBOT_SMOKE_TARGET (default: app.main). Exits non-zero on
any failure so CI can gate on it.
"""
import base64, hashlib, hmac, importlib, json, os, sys, threading
from http.server import BaseHTTPRequestHandler, HTTPServer

SECRET = "testsecret"
captured = []

class _Fake(BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        captured.append(json.loads(self.rfile.read(n).decode()))
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(json.dumps({"sentMessages": [{"id": "1", "quoteToken": "qt"}]}).encode())
    def log_message(self, *a): pass

srv = HTTPServer(("127.0.0.1", 0), _Fake)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()

# Env MUST be set before importing the target (config.py reads env at import).
os.environ.update(
    LINE_CHANNEL_SECRET=SECRET, LINE_CHANNEL_ACCESS_TOKEN="dummy",
    LINE_API_BASE=f"http://127.0.0.1:{port}", AI_PROVIDER="echo",
)
TARGET = os.getenv("LINEBOT_SMOKE_TARGET", "app.main")
mod = importlib.import_module(TARGET)
from starlette.testclient import TestClient
client = TestClient(mod.app)

def _event(text):
    return json.dumps({"destination": "U", "events": [{
        "type": "message", "mode": "active", "timestamp": 1700000000000,
        "source": {"type": "user", "userId": "U1"},
        "webhookEventId": "01H", "deliveryContext": {"isRedelivery": False},
        "replyToken": "RT", "message": {"id": "1", "type": "text", "text": text, "quoteToken": "q"},
    }]})

def _sign(body):
    return base64.b64encode(hmac.new(SECRET.encode(), body.encode(), hashlib.sha256).digest()).decode()

def _post(text, sig=None):
    captured.clear()
    body = _event(text)
    return client.post("/webhook/line", content=body,
                       headers={"X-Line-Signature": sig if sig is not None else _sign(body)})

failures = []
def check(cond, label):
    if not cond:
        failures.append(label)

try:
    r = _post("/ping")
    check(r.status_code == 200, "ping status 200")
    check(bool(captured) and captured[0]["messages"][0]["text"] == "pong", "ping -> pong")

    r = _post("營業時間")
    check(bool(captured) and captured[0]["messages"][0]["text"].startswith("我們的營業時間"), "keyword hours reply")

    r = _post("hello there")
    check(bool(captured) and captured[0]["messages"][0]["text"] == "LINE AI echo: hello there", "echo reply")

    r = _post("/ping", sig="invalidsignature")
    check(r.status_code == 403, "bad signature -> 403")
    check(not captured, "bad signature -> no reply sent")
finally:
    srv.shutdown()

if failures:
    print("FAIL:", "; ".join(failures), file=sys.stderr)
    sys.exit(1)
print(f"OK: parity checks passed (target={TARGET})")
```

- [ ] **Step 4: Modify `app/line.py`** — remove the inlined `KEYWORD_REPLIES` + reply logic, use the shared `resolve_reply`, and send replies via `LINE_API_BASE`. Replace the whole file with:

```python
import base64, hashlib, hmac, os, httpx
from .config import LINE_CHANNEL_SECRET, LINE_CHANNEL_ACCESS_TOKEN, AI_PROVIDER, LINE_API_BASE
from .bot import resolve_reply
def verify_signature(body, signature):
    # SECURITY: fail-closed by default.
    # If no channel secret is configured we cannot verify the LINE signature.
    # Accepting such requests would let anyone forge a webhook call, so we only
    # allow it through in an explicit local dev / echo context:
    #   - AI_PROVIDER == "echo"          (harmless echo bot, no real AI/secrets)
    #   - LINE_ALLOW_INSECURE == "1"     (operator explicitly opted in)
    if not LINE_CHANNEL_SECRET:
        if AI_PROVIDER == "echo" or os.getenv("LINE_ALLOW_INSECURE") == "1":
            return True
        return False
    expected=base64.b64encode(hmac.new(LINE_CHANNEL_SECRET.encode(),body,hashlib.sha256).digest()).decode()
    return hmac.compare_digest(expected, signature)
async def handle_events(payload):
    for e in payload.get("events",[]):
        if e.get("type")!="message" or e.get("message",{}).get("type")!="text": continue
        await reply_text(e["replyToken"], await resolve_reply(e["message"]["text"]))
async def reply_text(token,text):
    async with httpx.AsyncClient(timeout=30) as c:
        await c.post(LINE_API_BASE+"/v2/bot/message/reply",headers={"Authorization":"Bearer "+LINE_CHANNEL_ACCESS_TOKEN},json={"replyToken":token,"messages":[{"type":"text","text":text}]})
```

- [ ] **Step 5: Run the parity smoke test against the hand-rolled app — must pass.**

Run: `cd /home/ct/linebot-ai-starter && uv sync && PYTHONPATH=. uv run python parity_smoke_test.py`
Expected: `OK: parity checks passed (target=app.main)`, exit 0. (A StarletteDeprecationWarning may print — ignore.)

- [ ] **Step 6: Verify the failure path.**

Run: `PYTHONPATH=. LINEBOT_SMOKE_TARGET=app.nonexistent uv run python parity_smoke_test.py; echo "exit=$?"`
Expected: non-zero exit (import error).

- [ ] **Step 7: Commit.**

```bash
git add app/bot.py app/config.py app/line.py parity_smoke_test.py
git commit -m "refactor: extract shared resolve_reply + configurable LINE_API_BASE, add parity smoke test"
```

---

## Task 2: Add the line-bot-sdk optional extra

**Files:** Modify `pyproject.toml`; regenerate `uv.lock`.

- [ ] **Step 1: Edit `pyproject.toml`.** Add this section after the existing `dependencies = [...]` array (keep `[tool.uv] package = false` as-is; do NOT add line-bot-sdk to the required `dependencies`):

```toml
[project.optional-dependencies]
sdk = ["line-bot-sdk>=3,<4"]
```

- [ ] **Step 2: Regenerate the lock and confirm the base install excludes the SDK.**

Run: `uv lock && uv sync && uv run python -c "import importlib.util; print('linebot present:', importlib.util.find_spec('linebot') is not None)"`
Expected: `linebot present: False` (the SDK is NOT installed without the extra).

- [ ] **Step 3: Confirm the extra installs line-bot-sdk 3.x.**

Run: `uv sync --extra sdk && uv run python -c "import linebot; print(linebot.__version__)"`
Expected: prints `3.23.x` (or another `3.x`).

- [ ] **Step 4: Restore the base env for the next task.**

Run: `uv sync`

- [ ] **Step 5: Commit.**

```bash
git add pyproject.toml uv.lock
git commit -m "build: add optional line-bot-sdk extra (sdk)"
```

---

## Task 3: SDK implementation (signature / parse / reply)

**Files:** Create `app/line_sdk.py`, `app/main_sdk.py`.

- [ ] **Step 1: Create `app/line_sdk.py`** (SDK version of the three LINE concerns; text-only for now — the Quick Reply bonus is Task 4):

```python
"""line-bot-sdk v3 implementation of the same three LINE concerns the hand-rolled
app/line.py does: signature verification, event parsing, and the Reply API.
Reuses app/bot.py:resolve_reply so behavior matches the hand-rolled version.
Requires the `sdk` extra: uv sync --extra sdk."""
import json, os
from fastapi import HTTPException
from .config import LINE_CHANNEL_SECRET, LINE_CHANNEL_ACCESS_TOKEN, AI_PROVIDER, LINE_API_BASE
from .bot import resolve_reply
from linebot.v3 import WebhookParser
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.messaging import (
    Configuration, AsyncApiClient, AsyncMessagingApi, ReplyMessageRequest, TextMessage,
)

_parser = WebhookParser(LINE_CHANNEL_SECRET) if LINE_CHANNEL_SECRET else None


def _dev_insecure_ok() -> bool:
    # Mirror app/line.py's fail-closed policy for the no-secret case.
    return AI_PROVIDER == "echo" or os.getenv("LINE_ALLOW_INSECURE") == "1"


def _extract_events(body: str, signature: str):
    """Return a list of (text, reply_token). Raises HTTPException(403) on a bad
    or unverifiable signature, matching the hand-rolled behavior."""
    if _parser is None:
        if not _dev_insecure_ok():
            raise HTTPException(403, "Invalid LINE signature")
        return [(e["message"]["text"], e["replyToken"])
                for e in json.loads(body).get("events", [])
                if e.get("type") == "message" and e.get("message", {}).get("type") == "text"]
    try:
        parsed = _parser.parse(body, signature)
    except InvalidSignatureError:
        raise HTTPException(403, "Invalid LINE signature")
    return [(ev.message.text, ev.reply_token) for ev in parsed
            if isinstance(ev, MessageEvent) and isinstance(ev.message, TextMessageContent)]


async def process_webhook(raw_body: bytes, signature: str) -> None:
    events = _extract_events(raw_body.decode(), signature)
    if not events:
        return
    config = Configuration(host=LINE_API_BASE, access_token=LINE_CHANNEL_ACCESS_TOKEN or "dummy")
    async with AsyncApiClient(config) as api_client:
        api = AsyncMessagingApi(api_client)
        for text, token in events:
            reply = await resolve_reply(text)
            await api.reply_message(
                ReplyMessageRequest(reply_token=token, messages=[TextMessage(text=reply)])
            )
```

- [ ] **Step 2: Create `app/main_sdk.py`** (FastAPI app, parallels app/main.py):

```python
"""LINE Bot AI Starter — line-bot-sdk version. Run with:
    uvicorn app.main_sdk:app
Requires the `sdk` extra: uv sync --extra sdk."""
from fastapi import FastAPI, Request, Header
from .line_sdk import process_webhook

app = FastAPI(title="LINE Bot AI Starter (line-bot-sdk)")


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/webhook/line")
async def webhook(request: Request, x_line_signature: str = Header(default="")):
    await process_webhook(await request.body(), x_line_signature)
    return {"ok": True}
```

- [ ] **Step 3: Run the SAME parity smoke test against the SDK app — must pass identically.**

Run: `uv sync --extra sdk && PYTHONPATH=. LINEBOT_SMOKE_TARGET=app.main_sdk uv run python parity_smoke_test.py`
Expected: `OK: parity checks passed (target=app.main_sdk)`, exit 0.

- [ ] **Step 4: Confirm the hand-rolled app still passes (no regression).**

Run: `PYTHONPATH=. uv run python parity_smoke_test.py`
Expected: `OK: parity checks passed (target=app.main)`.

- [ ] **Step 5: Commit.**

```bash
git add app/line_sdk.py app/main_sdk.py
git commit -m "feat: line-bot-sdk implementation with the same webhook behavior"
```

---

## Task 4: Quick Reply bonus (SDK-only typed rich message)

**Files:** Modify `app/line_sdk.py`; Create `bonus_smoke_test_sdk.py`.

- [ ] **Step 1: Write the bonus smoke test (this is the test).** Create `bonus_smoke_test_sdk.py`:

```python
#!/usr/bin/env python3
"""Bonus check for the SDK-only Quick Reply rich message. The hand-rolled app
has no equivalent, so this runs only against app.main_sdk (CI's sdk track)."""
import base64, hashlib, hmac, importlib, json, os, sys, threading
from http.server import BaseHTTPRequestHandler, HTTPServer

SECRET = "testsecret"
captured = []

class _Fake(BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        captured.append(json.loads(self.rfile.read(n).decode()))
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(json.dumps({"sentMessages": [{"id": "1", "quoteToken": "qt"}]}).encode())
    def log_message(self, *a): pass

srv = HTTPServer(("127.0.0.1", 0), _Fake)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()

os.environ.update(
    LINE_CHANNEL_SECRET=SECRET, LINE_CHANNEL_ACCESS_TOKEN="dummy",
    LINE_API_BASE=f"http://127.0.0.1:{port}", AI_PROVIDER="echo",
)
mod = importlib.import_module("app.main_sdk")
from starlette.testclient import TestClient
client = TestClient(mod.app)

body = json.dumps({"destination": "U", "events": [{
    "type": "message", "mode": "active", "timestamp": 1700000000000,
    "source": {"type": "user", "userId": "U1"},
    "webhookEventId": "01H", "deliveryContext": {"isRedelivery": False},
    "replyToken": "RT", "message": {"id": "1", "type": "text", "text": "選單", "quoteToken": "q"},
}]})
sig = base64.b64encode(hmac.new(SECRET.encode(), body.encode(), hashlib.sha256).digest()).decode()

failures = []
try:
    client.post("/webhook/line", content=body, headers={"X-Line-Signature": sig})
    msg = captured[0]["messages"][0] if captured else {}
    if "quickReply" not in msg:
        failures.append(f"expected quickReply in reply message, got keys {list(msg)}")
    else:
        items = msg["quickReply"].get("items", [])
        if not items:
            failures.append("quickReply has no items")
finally:
    srv.shutdown()

if failures:
    print("FAIL:", "; ".join(failures), file=sys.stderr)
    sys.exit(1)
print("OK: SDK Quick Reply bonus check passed")
```

- [ ] **Step 2: Run it to verify it FAILS (no 選單 handling yet).**

Run: `uv sync --extra sdk && PYTHONPATH=. uv run python bonus_smoke_test_sdk.py; echo "exit=$?"`
Expected: non-zero exit — the reply for 選單 is a plain text echo, no `quickReply`.

- [ ] **Step 3: Add the Quick Reply bonus to `app/line_sdk.py`.** Add this import to the `from linebot.v3.messaging import (...)` block (extend the parenthesized list):

```python
from linebot.v3.messaging import (
    Configuration, AsyncApiClient, AsyncMessagingApi, ReplyMessageRequest, TextMessage,
    QuickReply, QuickReplyItem, MessageAction,
)
```

Then add this helper above `process_webhook`:

```python
# BONUS (SDK-only): a typed Quick Reply. Hand-rolling this means assembling the
# nested quickReply JSON by hand; the SDK builds it from typed objects in a few
# lines. This is an awareness example of what the framework gives you for free.
_BONUS_KEYWORD = "選單"

def _quick_reply_message() -> TextMessage:
    return TextMessage(
        text="請選擇:",
        quick_reply=QuickReply(items=[
            QuickReplyItem(action=MessageAction(label="營業時間", text="營業時間")),
            QuickReplyItem(action=MessageAction(label="Ping", text="/ping")),
        ]),
    )
```

And in `process_webhook`, replace the reply loop body so the bonus keyword short-circuits to the Quick Reply (everything else stays shared `resolve_reply`):

```python
        for text, token in events:
            if text == _BONUS_KEYWORD:
                message = _quick_reply_message()
            else:
                message = TextMessage(text=await resolve_reply(text))
            await api.reply_message(ReplyMessageRequest(reply_token=token, messages=[message]))
```

- [ ] **Step 4: Run the bonus test to verify it PASSES.**

Run: `PYTHONPATH=. uv run python bonus_smoke_test_sdk.py`
Expected: `OK: SDK Quick Reply bonus check passed`, exit 0.
(If the serialized field name differs from `quickReply`, inspect the captured body printed on failure and align the assertion/code — the SDK serializes camelCase, so `quickReply` is expected.)

- [ ] **Step 5: Re-run parity (bonus must NOT break the shared text surface).**

Run: `PYTHONPATH=. LINEBOT_SMOKE_TARGET=app.main_sdk uv run python parity_smoke_test.py`
Expected: `OK: parity checks passed (target=app.main_sdk)` (/ping, 營業時間, echo unaffected).

- [ ] **Step 6: Commit.**

```bash
git add app/line_sdk.py bonus_smoke_test_sdk.py
git commit -m "feat: SDK-only Quick Reply bonus with smoke check"
```

---

## Task 5: CI matrix (both tracks)

**Files:** Create `.github/workflows/ci.yml`.

- [ ] **Step 1: Create `.github/workflows/ci.yml`:**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  smoke-test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        track: [handrolled, sdk]
    steps:
      - uses: actions/checkout@v4
      - name: Install uv
        uses: astral-sh/setup-uv@v5

      # handrolled track: base deps, hand-rolled LINE integration
      - name: Sync (handrolled)
        if: matrix.track == 'handrolled'
        run: uv sync
      - name: Parity smoke against hand-rolled app
        if: matrix.track == 'handrolled'
        run: PYTHONPATH=. uv run python parity_smoke_test.py

      # sdk track: installs the extra, same parity test + bonus
      - name: Sync with sdk extra
        if: matrix.track == 'sdk'
        run: uv sync --extra sdk
      - name: Parity smoke against SDK app
        if: matrix.track == 'sdk'
        env:
          LINEBOT_SMOKE_TARGET: app.main_sdk
        run: PYTHONPATH=. uv run python parity_smoke_test.py
      - name: SDK Quick Reply bonus check
        if: matrix.track == 'sdk'
        run: PYTHONPATH=. uv run python bonus_smoke_test_sdk.py
```

- [ ] **Step 2: Validate YAML parses.**

Run: `uv run --with pyyaml python -c "import yaml; d=yaml.safe_load(open('.github/workflows/ci.yml')); print('yaml ok', d['jobs']['smoke-test']['strategy']['matrix']['track'])"`
Expected: `yaml ok ['handrolled', 'sdk']`.

- [ ] **Step 3: Locally simulate both tracks.**

Run:
```bash
uv sync && PYTHONPATH=. uv run python parity_smoke_test.py
uv sync --extra sdk && PYTHONPATH=. LINEBOT_SMOKE_TARGET=app.main_sdk uv run python parity_smoke_test.py && PYTHONPATH=. uv run python bonus_smoke_test_sdk.py
uv sync
```
Expected: three `OK:` lines.

- [ ] **Step 4: Commit.**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: matrix runs handrolled + sdk tracks (parity + bonus)"
```

---

## Task 6: Write the lesson `docs/08-line-bot-sdk-comparison.md`

**Files:** Create `docs/08-line-bot-sdk-comparison.md`.

- [ ] **Step 1: Create the file** with this content (Traditional Chinese, matching the other docs; no emoji):

````markdown
# LINE Bot 入門模板：用官方 SDK 重寫(對照組)

前半段(`01`/`03`)你已經**手刻**了 LINE 整合的三件事:HMAC-SHA256 簽章驗證、webhook 事件解析、Reply API 呼叫。看懂了每一段在幹嘛。這一段是課程後半:同樣的功能,改用**官方 `line-bot-sdk` v3**,讓你看到「同樣的事,SDK 少寫一大截」。

獨立的一課 —— 先跑過前半段、體會手刻的繁瑣,再回來看這段,對照最有感。

## 先講結論:差在哪

| 面向 | 完全手刻(`app/line.py`) | line-bot-sdk(`app/line_sdk.py`) |
|---|---|---|
| 簽章驗證 | `hmac.new` + `base64` + `compare_digest` | `WebhookParser(secret).parse(...)` |
| 事件解析 | raw dict:`e["message"]["text"]` | typed `MessageEvent` / `TextMessageContent` |
| Reply API | 手打 `httpx.post` 到 api.line.me + 自組 JSON | `AsyncMessagingApi.reply_message(ReplyMessageRequest(...))` |
| 回覆邏輯 | `resolve_reply()` | **共用同一個** `resolve_reply()` |
| 富訊息 | 自己拼巢狀 JSON | typed `QuickReply` / `FlexMessage` |

兩條核心訊息:

1. **SDK 幫你做掉協定樣板**:簽章、事件型別、Reply 的 JSON 形狀全包了。
2. **SDK 不幫你做你的 bot 邏輯**:`resolve_reply`(關鍵字表 + AI)兩版共用、完全相同 —— 框架換的是「跟 LINE 對話的管線」,不是「你的業務邏輯」。

## 步驟 1:裝 SDK(這就是第一個對照點)

前半段 `uv sync` 不需要 LINE 專用套件。SDK 版多一個相依,放在 optional extra:

```bash
uv sync --extra sdk
```

成功的話 `uv run python -c "import linebot; print(linebot.__version__)"` 會印出 `3.23.x`。

## 步驟 2:看 `app/line_sdk.py`

三件事各自縮短:

```python
from linebot.v3 import WebhookParser
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import AsyncMessagingApi, ReplyMessageRequest, TextMessage

# 簽章 + 解析:一行 parse,壞簽章自己拋 InvalidSignatureError
events = WebhookParser(secret).parse(body, signature)
text = events[0].message.text          # typed,不用 e["message"]["text"]

# Reply:typed request,不用自己組 JSON / 設 Authorization header
await api.reply_message(ReplyMessageRequest(
    reply_token=events[0].reply_token, messages=[TextMessage(text="pong")]))
```

對照手刻版:你不用自己算 HMAC、不用 raw dict 取值、不用記 Reply API 的 URL 與 JSON 形狀。唯一「不變」的是 `resolve_reply` —— 那是你的 bot 邏輯,框架不會替你寫。

## 步驟 3:跑同一份 parity 測試

關鍵設計:`parity_smoke_test.py` 用 `LINEBOT_SMOKE_TARGET` 切換 `app.main`(手刻)或 `app.main_sdk`(SDK),**同一組斷言對兩邊都過** —— 證明行為完全相同。它用一個本地假 LINE server 接住兩版送出的 Reply,再比對內容。

```bash
# SDK 版
uv sync --extra sdk
PYTHONPATH=. LINEBOT_SMOKE_TARGET=app.main_sdk uv run python parity_smoke_test.py
# 手刻版(預設)
PYTHONPATH=. uv run python parity_smoke_test.py
```

兩邊都會收尾 `OK: parity checks passed (target=...)`:有效簽章 + `/ping` → 回 `pong`、`營業時間` → 回營業字串、其他 → `LINE AI echo: ...`、無效簽章 → 403 且不送 reply。同樣的行為,兩種寫法。

## 步驟 4:SDK 才給得起的紅利 —— Quick Reply

手刻版只能回純文字(要回按鈕選單,得自己拼一坨巢狀 `quickReply` JSON)。SDK 用 typed 物件幾行搞定。傳 `選單` 給 SDK 版會回帶按鈕的 Quick Reply:

```python
from linebot.v3.messaging import TextMessage, QuickReply, QuickReplyItem, MessageAction

TextMessage(text="請選擇:", quick_reply=QuickReply(items=[
    QuickReplyItem(action=MessageAction(label="營業時間", text="營業時間")),
    QuickReplyItem(action=MessageAction(label="Ping", text="/ping")),
]))
```

驗證(手刻版沒有,所以是獨立一支測試):

```bash
PYTHONPATH=. uv run python bonus_smoke_test_sdk.py
```

成功會看到 `OK: SDK Quick Reply bonus check passed`。同樣的概念可以延伸到 Flex Message(卡片)等更豐富的訊息型別。

## 步驟 5:部署(跟前半段一樣是 webhook)

SDK 版是另一個 FastAPI app,啟動只差模組名:

```bash
uv run uvicorn app.main_sdk:app --host 0.0.0.0 --port 8000
```

webhook 路徑、簽章驗證、`.env` 設定都跟 `04-deployment.md` 一樣;LINE 平台那端的設定完全不變。

## 何時選哪一種

- **手刻**(前半段):學習、看懂簽章/協定、極簡或不想多帶相依的場景。
- **SDK**(這一段):實際出貨、要 Quick Reply / Flex 等富訊息、長期維護 —— 少寫一堆樣板,專注在你的 bot 邏輯。

先手刻看懂底層,再用 SDK 拿生產力,你會更清楚框架替你做了什麼、又沒替你做什麼(例如你的 `resolve_reply` 永遠是你自己的)。
````

- [ ] **Step 2: Verify the doc's commands actually work.**

Run: `uv sync --extra sdk && PYTHONPATH=. LINEBOT_SMOKE_TARGET=app.main_sdk uv run python parity_smoke_test.py && PYTHONPATH=. uv run python bonus_smoke_test_sdk.py`
Expected: both OK lines. If any quoted command/behavior differs, fix the doc to match reality.

- [ ] **Step 3: Commit.**

```bash
git add docs/08-line-bot-sdk-comparison.md
git commit -m "docs: add line-bot-sdk comparison second-half lesson (08)"
```

---

## Task 7: Reframe `docs/00-overview.md` as two tracks

**Files:** Modify `docs/00-overview.md`.

- [ ] **Step 1: Read the current file:** `cat docs/00-overview.md`.

- [ ] **Step 2: Insert a "兩軌" section** after the first intro paragraph (before the next `##` heading). Insert verbatim:

```markdown
## 兩軌:先手刻、再 SDK

這份教材分兩段:

- **前半段(`01`、`03`)** — 從零手刻 LINE 整合:HMAC 簽章驗證、webhook 事件解析、Reply API,看懂協定本身。
- **後半段(`08`)** — 用官方 **line-bot-sdk** 重寫同樣的功能當對照組,體會「同樣的事,SDK 少寫一大截」,並認識 Quick Reply 等 typed 富訊息。

先手刻看懂底層,再用 SDK 拿生產力 —— 你會更清楚框架替你做了什麼、又沒替你做什麼(你的 bot 邏輯 `resolve_reply` 永遠是你自己的)。
```

- [ ] **Step 3: If the file lists the doc series, add an entry** for `08-line-bot-sdk-comparison.md` (`用官方 SDK 重寫的對照組 + Quick Reply 紅利`), matching the existing list format. If there is no such list, skip.

- [ ] **Step 4: Verify no emoji and read naturally.**

Run: `grep -nP "[\x{1F000}-\x{1FAFF}\x{2600}-\x{27BF}\x{2B00}-\x{2BFF}]" docs/00-overview.md || echo "no emoji"`
Expected: `no emoji`.

- [ ] **Step 5: Commit.**

```bash
git add docs/00-overview.md
git commit -m "docs: reframe overview as two tracks (hand-rolled + SDK)"
```

---

## Task 8: Mirror Part 2 into `tutorial.html`

**Files:** Modify `tutorial.html`.

- [ ] **Step 1: Read the file:** `cat tutorial.html` — study its `<section>`/`<h2>`/`<h3>`/`<pre><code>`/`<table>` conventions, the header TOC (a list of `docs/NN` links), and where `<main>` ends.

- [ ] **Step 2: Add `08` to the header TOC.** Find the last TOC anchor (the `07-...` link) and add an `08-line-bot-sdk-comparison` anchor immediately after it, matching the existing `<a href='docs/NN-...'>NN-...</a>` format.

- [ ] **Step 3: Append a Part 2 `<section>`** inside `<main>`, after the last existing section and before `</main>`, mirroring `docs/08-line-bot-sdk-comparison.md`. Use the file's existing element conventions. Include, with content matching docs/08 verbatim: the differences table, `uv sync --extra sdk`, the `WebhookParser`/`reply_message` snippet, the `LINEBOT_SMOKE_TARGET=app.main_sdk uv run python parity_smoke_test.py` step with the "same test passes both" note, and the Quick Reply bonus snippet + `bonus_smoke_test_sdk.py` command.

- [ ] **Step 4: Verify HTML parses, no emoji, closing tags intact.**

Run:
```bash
uv run python -c "import html.parser; html.parser.HTMLParser().feed(open('tutorial.html').read()); print('html ok')"
grep -nP "[\x{1F000}-\x{1FAFF}\x{2600}-\x{27BF}\x{2B00}-\x{2BFF}]" tutorial.html || echo "no emoji"
```
Expected: `html ok` and `no emoji`. Confirm the file still ends with `</body></html>`.

- [ ] **Step 5: Commit.**

```bash
git add tutorial.html
git commit -m "docs: mirror SDK Part 2 into tutorial.html + TOC"
```

---

## Task 9: Surface the two-track structure in README / index / DESIGN

**Files:** Modify `README.md`, `index.html`, `DESIGN.md`.

- [ ] **Step 1: Read all three** to find the exact insertion points: `cat README.md DESIGN.md`; for index.html inspect the "解決什麼" / features card.

- [ ] **Step 2: `README.md`** — add to the Features/功能 list (match existing bullet style):

```markdown
- 官方 line-bot-sdk 版同功能重寫(optional `sdk` extra)— 見 `docs/08-line-bot-sdk-comparison.md`
```

And after the existing Quick start / run instructions, add:

````markdown
### 後半段:官方 SDK 版(對照組)

```bash
uv sync --extra sdk
PYTHONPATH=. LINEBOT_SMOKE_TARGET=app.main_sdk uv run python parity_smoke_test.py  # 同一份測試也過
uv run uvicorn app.main_sdk:app   # 啟動 SDK 版
```
````

If README has a docs/ link list, also add: `- 後半段(SDK 對照組):docs/08-line-bot-sdk-comparison.md`.

- [ ] **Step 3: `DESIGN.md`** — in the 功能賣點/features list, add a line:

```markdown
- 內建官方 SDK 對照組(後半段 `docs/08`):同功能用 line-bot-sdk 重寫,示範 Quick Reply 等 typed 富訊息
```

(If DESIGN.md already has a line about "可延伸到 SDK / 進階", adjust it to point at the now built-in docs/08 instead of duplicating.)

- [ ] **Step 4: `index.html`** — in the features card (the `<ul>` describing what the template offers), add one `<li>` matching the sibling `<li>` structure:

```html
<li><span>後半段用官方 line-bot-sdk 重寫同功能(對照組),示範 Quick Reply 富訊息</span></li>
```

- [ ] **Step 5: Verify.**

Run:
```bash
uv run python -c "import html.parser; html.parser.HTMLParser().feed(open('index.html').read()); print('index ok')"
test -f docs/08-line-bot-sdk-comparison.md && echo "link target exists"
grep -nP "[\x{1F000}-\x{1FAFF}\x{2600}-\x{27BF}\x{2B00}-\x{2BFF}]" README.md DESIGN.md index.html || echo "no emoji"
```
Expected: `index ok`, `link target exists`, `no emoji`.

- [ ] **Step 6: Commit.**

```bash
git add README.md index.html DESIGN.md
git commit -m "docs: surface the line-bot-sdk second-half track in README/index/DESIGN"
```

---

## Final verification (after all tasks)

- [ ] **Both tracks green:**

```bash
uv sync && PYTHONPATH=. uv run python parity_smoke_test.py
uv sync --extra sdk && PYTHONPATH=. LINEBOT_SMOKE_TARGET=app.main_sdk uv run python parity_smoke_test.py
PYTHONPATH=. uv run python bonus_smoke_test_sdk.py
uv sync
```
Expected: three `OK:` lines.

- [ ] **No emoji drift across docs:**

```bash
grep -rnP "[\x{1F000}-\x{1FAFF}\x{2600}-\x{27BF}\x{2B00}-\x{2BFF}]" docs/ README.md DESIGN.md tutorial.html index.html || echo "clean"
```

- [ ] **Optional live check:** run `uv run uvicorn app.main_sdk:app` and confirm it boots; or register in Claude as an MCP-adjacent webhook is N/A here (this is a LINE webhook, not MCP) — skip the Claude-mount step that applied to mcp-server-starter.

---

## Self-review notes (author)

- **Spec coverage:** §4 two-track → Tasks 1/3/6/7; §3 SDK facts → Tasks 3/4 (verified); §5 parity (local fake LINE + LINEBOT_SMOKE_TARGET) → Task 1 test, proven both targets in scratch; §6 Quick Reply bonus → Task 4; §7 fail-closed parity → Task 3 `_dev_insecure_ok` + parity bad-sig assertion; §8 files → Tasks 1-9; optional `sdk` extra → Task 2; CI matrix → Task 5.
- **Placeholder scan:** all code blocks complete and (for the load-bearing parity harness + SDK reply/parse) scratch-verified against line-bot-sdk 3.23.0; doc tasks 7-9 give exact insert blocks; tutorial task reads the file first because it adapts to existing structure, but the content to insert is fully specified.
- **Name consistency:** `resolve_reply`, `KEYWORD_REPLIES`, `LINE_API_BASE`, `process_webhook`, `_extract_events`, `_dev_insecure_ok`, `_quick_reply_message`, `_BONUS_KEYWORD="選單"`, env `LINEBOT_SMOKE_TARGET`, extra `sdk`, apps `app.main` / `app.main_sdk` — consistent across tasks.
