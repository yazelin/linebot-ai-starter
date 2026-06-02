# LINE Bot AI 入門模板：完整操作流程

這章帶你走一遍：先在本機把簽章驗證跑出 200/403、再親手重現「忘了設 secret 會被擋」的行為、然後找到回覆邏輯在哪裡改，最後做一個你自己動手的小練習，並看到改前改後的真實差異。

整章除了最後「要上線」的提醒外，都不需要 LINE 帳號。

## 步驟 1：echo 模式啟動

保持 `.env` 的 `AI_PROVIDER=echo`，啟動：

```bash
uvicorn app.main:app --reload --port 8000
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

執行 `python sig_demo.py`，本機模擬簽章驗證的真實輸出：

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

執行 `python failclosed_demo.py`，真實輸出：

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

bot 收到文字訊息後怎麼決定回什麼，全在 `app/line.py` 的 `handle_events`：

```python
async def handle_events(payload):
    for e in payload.get("events",[]):
        if e.get("type")!="message" or e.get("message",{}).get("type")!="text": continue
        text=e["message"]["text"]; reply="pong" if text=="/ping" else await ask_ai(text)
        await reply_text(e["replyToken"], reply[:4500])
```

讀法：

- `/ping` 直接回 `pong`。
- 其他訊息丟給 `ask_ai`（在 `app/ai.py`）。
- echo 模式下 `ask_ai` 回 `"LINE AI echo: " + text`。

所以「改 bot 怎麼回話」有兩個地方：
- 想加固定關鍵字回覆 -> 改 `app/line.py` 的 `handle_events`。
- 想改 AI 怎麼回 / 換 provider -> 改 `app/ai.py` 的 `ask_ai`。

## 步驟 5：動手練習 — 加一個關鍵字自動回覆

目標：使用者打「營業時間」時，直接回固定答案，不要丟給 AI。

### 改之前，先看現狀

我們不需要真的 LINE token 也能看「bot 會回什麼」——把 `reply_text`（真正打 LINE API 的函式）換成一個只記錄文字的假函式即可。存成 `exercise.py`：

```python
import asyncio, os
os.environ["AI_PROVIDER"] = "echo"; os.environ["LINE_CHANNEL_ACCESS_TOKEN"] = "dummy"
import app.line as line

captured = []
async def fake_reply(token, text): captured.append(text)
line.reply_text = fake_reply   # 攔截回覆，不真的打 LINE API（那需要真 token）

async def main():
    for msg in ["/ping", "hello", "營業時間"]:
        captured.clear()
        await line.handle_events({"events":[{"type":"message","replyToken":"TK",
            "message":{"type":"text","text":msg}}]})
        print(f"輸入 {msg!r:10} -> 回覆 {captured[0]!r}")

asyncio.run(main())
```

執行 `python exercise.py`，改之前的真實輸出：

```
輸入 '/ping'    -> 回覆 'pong'
輸入 'hello'    -> 回覆 'LINE AI echo: hello'
輸入 '營業時間'    -> 回覆 'LINE AI echo: 營業時間'
```

「營業時間」現在被當成一般訊息丟給 echo，回了沒用的內容。

### 改成這樣

在 `app/line.py`，把 `handle_events` 上面加一張關鍵字表，並讓 handler 先查表：

```python
# 關鍵字自動回覆表：訊息文字完全相符時，直接回固定字串，不經過 AI。
KEYWORD_REPLIES = {
    "/ping": "pong",
    "營業時間": "我們的營業時間是週一到週五 09:00-18:00。",
}
async def handle_events(payload):
    for e in payload.get("events",[]):
        if e.get("type")!="message" or e.get("message",{}).get("type")!="text": continue
        text=e["message"]["text"]
        # 先比對關鍵字表；沒命中才交給 AI provider。
        reply=KEYWORD_REPLIES[text] if text in KEYWORD_REPLIES else await ask_ai(text)
        await reply_text(e["replyToken"], reply[:4500])
```

### 改完跑出來變這樣

再跑一次 `python exercise.py`，改之後的真實輸出：

```
輸入 '/ping'    -> 回覆 'pong'
輸入 'hello'    -> 回覆 'LINE AI echo: hello'
輸入 '營業時間'    -> 回覆 '我們的營業時間是週一到週五 09:00-18:00。'
```

`'營業時間'` 那行從 echo 變成你的固定答案，其它訊息照舊。練習完成。

> 想自己延伸：在 `KEYWORD_REPLIES` 多加幾組（例如 `"地址": "..."`、`"菜單": "..."`），再跑一次 `exercise.py` 確認命中。沒命中的訊息會繼續走 AI，這就是「FAQ 直答 + 其餘問 AI」最小的混合策略。

## 要讓真的 LINE 使用者收到（需要你的 channel）

本機驗證 OK 後，照 `01-quickstart.md` 最後一段：在 LINE Developers console 拿 channel secret / access token、用 ngrok 開公開 HTTPS、把 `https://你的網域/webhook/line` 設成 webhook URL、開 Use webhook、關 Auto-reply。設好你的 channel access token 後，傳「營業時間」就會在 LINE 裡收到你剛寫的固定回覆。
