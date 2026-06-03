# Design: linebot Part 2 — 官方 line-bot-sdk 對照組

- **Date:** 2026-06-03
- **Repo:** `linebot-ai-starter`
- **Status:** Approved design (pending written-spec review)

## 1. 目標與動機

前半段教學帶學員**手刻** LINE 整合的三件事:HMAC-SHA256 簽章驗證、webhook 事件解析、Reply API 呼叫(全用 stdlib + httpx)。手刻的好處是看懂每一段在幹嘛,但繁瑣且容易出錯。

後半段新增一段**獨立課程**:用**官方 `line-bot-sdk` v3**(async)重寫**完全相同的功能**當對照組,讓學員體會「同樣的事,SDK 少寫一大截」,並認識 SDK 才給得起的紅利(Quick Reply 等 typed 富訊息)。這是 `mcp-server-starter` 已驗證成功的「手刻 → 框架」教學模式套到 LINE 場景。

非目標:不改 Part 1 的行為;不換掉 AI provider 層(`ai.py` 不動);transport 不變(都是 FastAPI webhook)。

## 2. 與 mcp-server-starter 的關鍵差異

- 本 repo **不是零相依**:`pyproject.toml` 已有必需相依(fastapi/uvicorn/httpx/python-dotenv)且 `[tool.uv] package = false`。所以這裡 optional extra 的意義是**隔離 SDK**(讓 Part 1 / base 安裝不被 SDK 影響),不是「保零相依」。
- 沒有 console script(`package = false`):Part 1 用 `uvicorn app.main:app` 跑;Part 2 用 `uvicorn app.main_sdk:app` 跑。
- 本 repo **目前零測試**:這次要從零建立 smoke test + CI。
- 對外要打 LINE Reply API,所以 parity 驗證用「本地假 LINE server」端對端(見 §5)。

## 3. 已驗證的技術事實(line-bot-sdk 3.23.0,實測)

- `Configuration(host=...)` 可覆寫 API base → SDK 的 reply 可導向本地假 server。
- `AsyncMessagingApi.reply_message(ReplyMessageRequest(reply_token=..., messages=[TextMessage(text=...)]))` 會 POST 到 `<host>/v2/bot/message/reply`,body `{"replyToken":...,"messages":[{"type":"text","text":...}], "notificationDisabled": false}` —— 與手刻版同路徑、同 body 形狀。
- 假 LINE server 必須回 `{"sentMessages":[{"id":"1","quoteToken":"qt"}]}`,否則 SDK 解析回應時拋 ValidationError。
- `WebhookParser(channel_secret).parse(body, signature)`:有效簽章 → `MessageEvent`(`ev.message.text` / `ev.reply_token`);無效 → `InvalidSignatureError`。
- **webhook fixture 必須是完整真實事件**:text message 需含 `quoteToken`,且事件需有 `mode`/`timestamp`/`source`/`webhookEventId`/`deliveryContext`,否則 SDK 解析成 `UnknownEvent`(無 `.message`)。
- Flex/QuickReply typed model 都在(`FlexMessage`/`QuickReply`/`QuickReplyItem`/`MessageAction`)。

## 4. 架構(兩軌 + 共用 bot 邏輯)

| | Part 1（現有） | Part 2（新增） |
|---|---|---|
| 簽章驗證 | 手刻 `hmac`+`base64`+`compare_digest` | `WebhookParser` |
| 事件解析 | raw dict traversal | `parser.parse()` → typed `MessageEvent` |
| Reply | 手打 `httpx.post` 到 api.line.me | `AsyncMessagingApi.reply_message(...)` |
| 回覆邏輯 | `KEYWORD_REPLIES` + `ask_ai` + `[:4500]` | **共用同一份** `resolve_reply()` |
| 富訊息 | （無） | Quick Reply 紅利 |
| 啟動 | `uvicorn app.main:app` | `uvicorn app.main_sdk:app` |

**共用是「行為相同」的保證**:把回覆解析邏輯抽成 `app/bot.py` 的 `resolve_reply(text) -> str`,兩軌都呼叫它;只有 LINE 管線(簽章/解析/reply transport)不同。

## 5. parity 驗證(已驗證可行的核心)

- **本地假 LINE server**:smoke script 內起一個 threaded `http.server`,對 `POST /v2/bot/message/reply` 記錄收到的 body,並回 `{"sentMessages":[{"id":"1","quoteToken":"qt"}]}`。
- **兩軌 reply 都導向它**:手刻版讀 `LINE_API_BASE`(新增的可配置 base URL,預設 `https://api.line.me`);SDK 版用 `Configuration(host=LINE_API_BASE)`。
- **驅動**:用 FastAPI 內建 `TestClient`(starlette,httpx 既有相依,**不引 pytest**)對 webhook 端點 POST 一份**簽好章的完整 LINE 事件**。
- **斷言**(同一份,對兩 target 都跑 → 對等):
  - 有效簽章 + `/ping` → 200,假 server 收到 reply 文字 `pong`。
  - `營業時間` → 200,reply 為設定的營業字串。
  - 其他文字(echo 模式)→ 200,reply 為 `LINE AI echo: <text>`。
  - 無效簽章 → 403,假 server 沒收到任何 reply。
- **目標切換**:`LINEBOT_SMOKE_TARGET`(預設 `app.main`)選 `app.main` 或 `app.main_sdk`,完全比照 mcp 的 `MCP_SMOKE_TARGET`。

## 6. SDK 紅利(對等之外，認識 typed 富訊息）

- SDK 版多一條 branch:demo 關鍵字 `選單` → 回 **Quick Reply** 按鈕(typed `QuickReply`/`QuickReplyItem`/`MessageAction`)。手刻要自己拼巢狀 JSON,SDK 幾行 typed 物件搞定。
- **不進** `resolve_reply`(保 parity 表面乾淨),只在 SDK app 處理。
- `bonus_smoke_test_sdk.py`:對 SDK app POST `選單`,斷言假 server 收到的 reply body 含 `quickReply` 結構。
- docs/08 框成「框架還給你更多」。

## 7. 錯誤處理 / 邊界

- SDK 版**複製 Part 1 的 fail-closed 政策**:無 `LINE_CHANNEL_SECRET` 時,只在 `AI_PROVIDER=echo` 或 `LINE_ALLOW_INSECURE=1` 放行,否則拒(與手刻 `verify_signature` 一致)。有 secret 時 `WebhookParser` 失敗 → 403。
- reply 文字一律 `[:4500]` 截斷(沿用 Part 1)。

## 8. 檔案清單

### 程式碼
- **`app/bot.py`(新)** — `resolve_reply(text)` + `KEYWORD_REPLIES`(從 line.py 移來)。
- **`app/line.py`(改)** — 改用 `bot.resolve_reply`;Reply base URL 改 `LINE_API_BASE`(env,預設 `https://api.line.me`)。
- **`app/line_sdk.py`(新)** — SDK 簽章/解析/reply + Quick Reply 紅利;reply 用 `Configuration(host=LINE_API_BASE)`。
- **`app/main_sdk.py`(新)** — FastAPI app（對應 main.py，掛 SDK webhook）。
- **`pyproject.toml`(改)** — `[project.optional-dependencies] sdk = ["line-bot-sdk>=3,<4"]`;`package = false` 不變。
- **`uv.lock`（重產）**。

### 測試 / CI
- **`parity_smoke_test.py`(新)** — §5 的本地假 LINE + TestClient parity,`LINEBOT_SMOKE_TARGET` 切目標。
- **`bonus_smoke_test_sdk.py`(新)** — §6 Quick Reply 紅利（sdk-only）。
- **`.github/workflows/ci.yml`(新)** — matrix:`handrolled`(base 相依,target=app.main)/ `sdk`(`uv sync --extra sdk`,target=app.main + bonus)。

### 文件
- **`docs/08-line-bot-sdk-comparison.md`(新)** — 對照課:差異表、裝 extra、SDK 版逐段、parity「同一份測試兩邊過」、Quick Reply 紅利、何時選哪種、掛 Claude/LINE 平台。
- **`docs/00-overview.md`(改)** — 兩軌框架。
- **`tutorial.html`(改)** — Part 2 區塊 + TOC 補 08。
- **`README.md` / `index.html` / `DESIGN.md`(改)** — SDK 從「可延伸」升級為「內建後半段」。

## 9. 風險與待確認

- **line-bot-sdk 版本飄移**:鎖 `>=3,<4`,smoke test + CI 當防線;docs 標所用版本(3.23.x)。
- **fixture 真實性**:webhook fixture 必含 `quoteToken` 等完整欄位(已驗),否則 SDK 解析失敗 —— 測試會抓到。
- **fail-closed 政策一致性**:SDK 版需主動複製 Part 1 的 echo/INSECURE 放行邏輯,否則兩軌邊界行為不一致(parity 測試的無效簽章那條會抓到偏差)。
- **TestClient + async**:端點 async、手刻 reply 用 httpx.AsyncClient、SDK 用 aiohttp,假 server 是 threaded http.server —— 三者已個別驗證相容。

## 10. 不做（YAGNI）

- 不引入 pytest（沿用家族 plain-python smoke script 風格）。
- 不改 `ai.py` / AI provider 行為。
- 不把 Part 1 改成 SDK(手刻保留)。
- 不為 SDK 版加 console script（`package = false` 維持;用 `uvicorn app.main_sdk:app`）。
- transport 軸(raw polling/webhook → bot 框架)不做 —— 評估為弱對照。
