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
