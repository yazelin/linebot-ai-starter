# LINE Bot AI 入門模板：快速開始

這份是「照著打、看得到結果」的版本。每一步都有：要打的指令、跑完真實的輸出、以及「成功的話你會看到什麼」。

本機這一段（安裝、啟動、簽章驗證）完全不需要 LINE 帳號就能做完。最後要讓真的 LINE 使用者收到回覆，才需要你自己的 LINE channel；那一段會清楚標出來。

## 前置需求

- uv（Python 套件 / 環境管理器，會自動幫你準備對的 Python）
- Git
- 會用終端機
- 之後要接真實 LINE 才需要：一個 LINE 帳號、LINE Developers console

> 本專案用 uv 管理依賴與虛擬環境（pyproject.toml + uv.lock），不再手動 `python -m venv` + `pip`。

### 先裝 uv（一次就好）

Ubuntu / macOS：

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Windows（PowerShell）：

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

裝完重開終端機，`uv --version` 印得出版本就 OK。

## 第一步：取得程式碼並裝依賴

以下 `uv sync` / `uv run` 在 Ubuntu 與 Windows 完全相同。

```bash
git clone https://github.com/yazelin/linebot-ai-starter.git
cd linebot-ai-starter
uv sync
```

`uv sync` 會依 pyproject.toml + uv.lock 自動建立 `.venv` 並裝好套件（毋須手動 venv/activate）。成功的話你會看到（本機實際輸出）：

```
Using CPython 3.11.13
Creating virtual environment at: .venv
Resolved 24 packages in 19ms
Installed 21 packages in 8ms
 + fastapi==0.115.6
 + uvicorn==0.34.0
 + httpx==0.28.1
 + python-dotenv==1.0.1
 + starlette==0.41.3
 + pydantic==2.13.4
 ...（共 21 個套件）
```

之後加新套件用 `uv add <套件>`（會同時更新 pyproject 與 uv.lock）。沒裝 uv 的話 `pip install .` 也能裝，但本教學以 uv 為主。

## 第二步：準備環境變數

```bash
cp .env.example .env
```

`.env.example` 內容長這樣：

```
LINE_CHANNEL_SECRET=replace_me
LINE_CHANNEL_ACCESS_TOKEN=replace_me
AI_PROVIDER=echo
HTTP_LLM_ENDPOINT=https://api.openai.com/v1/chat/completions
HTTP_LLM_API_KEY=
MODEL_NAME=gpt-4o-mini
```

第一次先**不要動**，保持 `AI_PROVIDER=echo`。echo 模式不需要任何 LINE 金鑰或 AI key，最適合確認整條路通不通。

## 第三步：啟動服務

```bash
uv run uvicorn app.main:app --reload --port 8000
```

成功的話你會看到（這是本機實際輸出）：

```
INFO:     Started server process [790943]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

## 第四步：健康檢查

另開一個終端機（原本那個讓 uvicorn 繼續跑）：

```bash
curl http://127.0.0.1:8000/health
```

> Windows PowerShell 的 `curl` 是 `Invoke-WebRequest` 別名，建議改用 `curl.exe http://127.0.0.1:8000/health` 或 `Invoke-RestMethod http://127.0.0.1:8000/health`。Ubuntu 用一般 `curl` 即可。

成功的話你會看到：

```
{"ok":true}
```

同時 uvicorn 那邊會多印一行：

```
INFO:     127.0.0.1:54580 - "GET /health HTTP/1.1" 200 OK
```

看到 `{"ok":true}` 就代表服務有起來、路由有通。

## 第五步：本機模擬簽章驗證（不用 LINE 帳號）

LINE 送 webhook 時會附一個 `X-Line-Signature` header，那是用你的 channel secret 對 **raw body** 做 HMAC-SHA256 再 base64。`app/line.py` 真的會驗這個簽章。我們可以在本機自己算一個正確簽章來證明它有效，不需要真的 LINE 帳號。

把下面存成 `sig_demo.py`（放在 repo 根目錄）：

```python
import base64, hashlib, hmac, json, os
os.environ["LINE_CHANNEL_SECRET"] = "test_secret_123"
os.environ["LINE_CHANNEL_ACCESS_TOKEN"] = "dummy"
os.environ["AI_PROVIDER"] = "echo"

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
body = json.dumps({"events": []}).encode("utf-8")  # 空 events，不會去呼叫 reply API

def sign(secret, raw):
    return base64.b64encode(hmac.new(secret.encode(), raw, hashlib.sha256).digest()).decode()

good = sign("test_secret_123", body)
bad  = sign("WRONG_secret", body)

print("[valid]  ", client.post("/webhook/line", content=body,
      headers={"X-Line-Signature": good}).status_code)
print("[wrong]  ", client.post("/webhook/line", content=body,
      headers={"X-Line-Signature": bad}).status_code)
print("[missing]", client.post("/webhook/line", content=body).status_code)
```

執行（TestClient 需要 httpx，已在 dependencies 內）：

```bash
uv run python sig_demo.py
```

本機模擬簽章驗證的真實輸出：

```
[valid]   200
[wrong]   403
[missing] 403
```

成功的話你會看到：正確簽章回 `200`，錯誤或沒帶簽章回 `403`。這證明簽章驗證是真的在擋人，不是擺好看的。（這是本機模擬，不是真的 LINE 呼叫；測完可以把 `sig_demo.py` 刪掉。）

## 本機到此為止：你已經驗證的東西

- 服務能啟動（看到 `Application startup complete.`）
- `/health` 回 `{"ok":true}`
- 簽章正確放行、錯誤擋掉（200 / 403）
- secret 沒有 commit 進 GitHub（`.env` 已被 `.gitignore` 排除）

## 要讓真的 LINE 使用者收到回覆（需要你自己的 LINE channel）

以下步驟需要你自己的 LINE 帳號與外部服務，**這份文件沒辦法幫你跑**，但流程是固定的：

1. 到 LINE Developers console（developers.line.biz）建一個 **Messaging API channel**。
2. 在 channel 設定頁複製兩個值，填進 `.env`：
   - **Channel secret** -> `LINE_CHANNEL_SECRET`
   - **Channel access token**（要按發行）-> `LINE_CHANNEL_ACCESS_TOKEN`
3. 本機服務還在 `127.0.0.1`，LINE 連不到，要開一條公開 HTTPS 通道。最簡單用 ngrok：

   ```bash
   ngrok http 8000
   ```

   它會給你一個像 `https://xxxx.ngrok-free.app` 的網址。

4. 回 LINE console 的 Messaging API 頁，把 **Webhook URL** 設成：

   ```
   https://xxxx.ngrok-free.app/webhook/line
   ```

   並打開 **Use webhook**，關掉 **Auto-reply messages**（不然官方自動回覆會干擾你）。
5. 用手機加你的 bot 為好友，傳一句話。設好你的 channel access token 後，你會在 LINE 裡收到 `LINE AI echo: 你打的字`，uvicorn 那邊也會印出一行 `POST /webhook/line ... 200 OK`。

> 注意：回覆是透過 `POST https://api.line.me/v2/bot/message/reply` 加 Bearer token 送出，**一定要有真的 channel access token 才會成功**。token 沒設或設錯，webhook 收得到、但回覆會失敗（見 `05-common-pitfalls.md`）。

## 下一步

- 想知道每個檔案在做什麼：看 `02-architecture.md`
- 想完整帶一遍、含動手改回覆邏輯：看 `03-step-by-step.md`
- 卡住了：看 `05-common-pitfalls.md`
