# LINE Bot AI 入門模板：完整操作流程

這章帶你走一遍：先在本機把簽章驗證跑出 200/403、再親手重現「忘了設 secret 會被擋」的行為、然後找到回覆邏輯在哪裡改，最後做一個你自己動手的小練習，並看到改前改後的真實差異。

整章除了最後「要上線」的提醒外，都不需要 LINE 帳號。

## 步驟 1：echo 模式啟動

保持 `.env` 的 `AI_PROVIDER=echo`，啟動（`uv run` 在 Ubuntu 與 Windows 完全相同）：

```bash
uv run uvicorn app.main:app --reload --port 8000
```

看到這幾行就是起來了：

```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

## 步驟 2：本機模擬簽章驗證（看到 200 與 403）

`app/main.py` 收到 webhook 後，第一件事就是驗簽章：

```python
@app.post("/webhook/line")
async def webhook(request:Request, x_line_signature:str=Header(default="")):
    body=await request.body()
    if not verify_signature(body,x_line_signature): raise HTTPException(403,"Invalid LINE signature")
    await handle_events(await request.json()); return {"ok":True}
```

驗證本身在 `app/line.py` 的 `verify_signature`，核心是這一行——用 channel secret 對 **raw body** 算 HMAC-SHA256、base64、再用 `compare_digest` 做常數時間比對：

```python
expected=base64.b64encode(hmac.new(LINE_CHANNEL_SECRET.encode(),body,hashlib.sha256).digest()).decode()
return hmac.compare_digest(expected, signature)
```

我們在本機自己算一個正確簽章送進去。把下面存成 `sig_demo.py`：

```python
import base64, hashlib, hmac, json, os
os.environ["LINE_CHANNEL_SECRET"] = "test_secret_123"
os.environ["LINE_CHANNEL_ACCESS_TOKEN"] = "dummy"
os.environ["AI_PROVIDER"] = "echo"

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
body = json.dumps({"events": []}).encode("utf-8")

def sign(secret, raw):
    return base64.b64encode(hmac.new(secret.encode(), raw, hashlib.sha256).digest()).decode()

good = sign("test_secret_123", body)
bad  = sign("WRONG_secret", body)

print("[valid signature]  ", client.post("/webhook/line", content=body,
      headers={"X-Line-Signature": good}).status_code)
print("[wrong signature]  ", client.post("/webhook/line", content=body,
      headers={"X-Line-Signature": bad}).status_code)
print("[missing signature]", client.post("/webhook/line", content=body).status_code)
```

執行 `uv run python sig_demo.py`，本機模擬簽章驗證的真實輸出：

```
[valid signature]   200
[wrong signature]   403
[missing signature] 403
```

正確簽章放行、錯的擋掉。注意我們刻意送 `{"events": []}`（空清單），所以不會觸發任何回覆，不需要真的 LINE token 也能跑完。

## 步驟 3：親手重現 fail-closed（忘了設 secret 會怎樣）

這個 starter 的簽章驗證是 **fail-closed**：如果你**沒設** `LINE_CHANNEL_SECRET`，程式沒辦法驗簽章，預設就是**拒絕**——除非你明確處在安全的本機情境（`AI_PROVIDER=echo`，或自己設 `LINE_ALLOW_INSECURE=1`）。

對應 `app/line.py` 這段：

```python
if not LINE_CHANNEL_SECRET:
    if AI_PROVIDER == "echo" or os.getenv("LINE_ALLOW_INSECURE") == "1":
        return True
    return False
```

自己驗一次。存成 `failclosed_demo.py`：

```python
import json, os, sys
from fastapi.testclient import TestClient

def run(secret, provider, allow_insecure):
    os.environ["LINE_CHANNEL_SECRET"] = secret
    os.environ["AI_PROVIDER"] = provider
    if allow_insecure is None: os.environ.pop("LINE_ALLOW_INSECURE", None)
    else: os.environ["LINE_ALLOW_INSECURE"] = allow_insecure
    os.environ["LINE_CHANNEL_ACCESS_TOKEN"] = "dummy"
    for m in [m for m in sys.modules if m=="app" or m.startswith("app.")]:
        del sys.modules[m]          # 重新 import 讓 config 重讀環境變數
    from app.main import app
    body = json.dumps({"events": []}).encode("utf-8")
    r = TestClient(app).post("/webhook/line", content=body)  # 不帶簽章
    print(f"secret={'set' if secret else '(空)'}, AI_PROVIDER={provider}, "
          f"LINE_ALLOW_INSECURE={allow_insecure} -> {r.status_code}")

run("", "echo", None)
run("", "http", None)
run("", "http", "1")
```

執行 `uv run python failclosed_demo.py`，真實輸出：

```
secret=(空), AI_PROVIDER=echo, LINE_ALLOW_INSECURE=None -> 200
secret=(空), AI_PROVIDER=http, LINE_ALLOW_INSECURE=None -> 403
secret=(空), AI_PROVIDER=http, LINE_ALLOW_INSECURE=1 -> 200
```

解讀：

- echo 模式沒 secret 也放行（本機玩可以）。
- 一旦切到真 provider（`http`）又沒 secret，直接 403——這是在保護你，避免沒簽章驗證就上線被人偽造 webhook。
- 真的要在沒 secret 下放行（例如某些受控內網測試），得自己明確設 `LINE_ALLOW_INSECURE=1`。

**結論：正式上線一定要設真的 `LINE_CHANNEL_SECRET`。**

## 步驟 4：找到「回覆邏輯」在哪裡

bot 收到文字訊息後怎麼決定回什麼，集中在 `app/bot.py` 的 `resolve_reply`：

```python
from .ai import ask_ai

KEYWORD_REPLIES = {
    "/ping": "pong",
    "營業時間": "我們的營業時間是週一到週五 09:00-18:00。",
}

async def resolve_reply(text: str) -> str:
    reply = KEYWORD_REPLIES[text] if text in KEYWORD_REPLIES else await ask_ai(text)
    return reply[:4500]
```

讀法：

- 先比對 `KEYWORD_REPLIES`，完全相符就回固定字串（例如 `/ping` 回 `pong`、`營業時間` 回營業字串）。
- 沒命中才丟給 `ask_ai`（在 `app/ai.py`）；echo 模式下 `ask_ai` 回 `"LINE AI echo: " + text`。

`app/line.py` 的 `handle_events` 現在只是薄薄一層：解析事件、呼叫 `resolve_reply`、再用 `reply_text` 送出。把回覆邏輯抽出來的好處，在後半段 `08-line-bot-sdk-comparison.md` 會看到 —— 手刻版與 line-bot-sdk 版**共用同一個 `resolve_reply`**，所以兩種寫法行為完全相同。

所以「改 bot 怎麼回話」有兩個地方：
- 想加固定關鍵字回覆 -> 改 `app/bot.py` 的 `KEYWORD_REPLIES`。
- 想改 AI 怎麼回 / 換 provider -> 改 `app/ai.py` 的 `ask_ai`。

## 步驟 5：動手練習 — 加一個關鍵字自動回覆

目標：使用者打「地址」時，直接回固定答案，不要丟給 AI。（`營業時間` 已經內建在 `KEYWORD_REPLIES`，所以我們改用一個還沒內建的關鍵字來練習。）

### 改之前，先看現狀

不需要真的 LINE token 也能看「bot 會回什麼」—— 直接呼叫 `resolve_reply` 即可。存成 `exercise.py`：

```python
import asyncio, os
os.environ["AI_PROVIDER"] = "echo"
from app.bot import resolve_reply

async def main():
    for msg in ["/ping", "地址", "hello"]:
        print(f"輸入 {msg!r:8} -> 回覆 {(await resolve_reply(msg))!r}")

asyncio.run(main())
```

執行 `PYTHONPATH=. uv run python exercise.py`，改之前的真實輸出：

```
輸入 '/ping'  -> 回覆 'pong'
輸入 '地址'     -> 回覆 'LINE AI echo: 地址'
輸入 'hello'  -> 回覆 'LINE AI echo: hello'
```

「地址」現在被當成一般訊息丟給 echo，回了沒用的內容。

### 改成這樣

在 `app/bot.py` 的 `KEYWORD_REPLIES` 多加一行：

```python
KEYWORD_REPLIES = {
    "/ping": "pong",
    "營業時間": "我們的營業時間是週一到週五 09:00-18:00。",
    "地址": "我們的地址是台北市信義路五段 7 號。",
}
```

### 改完跑出來變這樣

再跑一次 `PYTHONPATH=. uv run python exercise.py`，改之後的真實輸出：

```
輸入 '/ping'  -> 回覆 'pong'
輸入 '地址'     -> 回覆 '我們的地址是台北市信義路五段 7 號。'
輸入 'hello'  -> 回覆 'LINE AI echo: hello'
```

`'地址'` 那行從 echo 變成你的固定答案，其它訊息照舊。練習完成。

> 想自己延伸：在 `KEYWORD_REPLIES` 多加幾組（例如 `"菜單": "..."`），再跑一次。沒命中的訊息會繼續走 AI，這就是「FAQ 直答 + 其餘問 AI」最小的混合策略。因為 `resolve_reply` 是兩版共用的，你加的關鍵字在手刻版與 line-bot-sdk 版都會生效。

## 要讓真的 LINE 使用者收到（需要你的 channel）

本機驗證 OK 後，照 `01-quickstart.md` 最後一段：在 LINE Developers console 拿 channel secret / access token、用 ngrok 開公開 HTTPS、把 `https://你的網域/webhook/line` 設成 webhook URL、開 Use webhook、關 Auto-reply。設好你的 channel access token 後，傳「營業時間」就會在 LINE 裡收到你剛寫的固定回覆。
