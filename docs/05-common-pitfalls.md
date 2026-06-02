# LINE Bot AI 入門模板：常見問題與踩雷清單

這裡的症狀盡量是「真的會看到的東西」，照著對症狀找原因最快。

## 1. 簽章驗證一直 403（明明 secret 是對的）

**症狀**：webhook 回 `403 {"detail":"Invalid LINE signature"}`，但你確定 channel secret 沒填錯。

**最常見原因**：簽章是對 **raw body 的 bytes** 算的。如果中間有人把 JSON 重新序列化（先 `json.loads` 再 `json.dumps`、或某些 proxy / API gateway 改了 body 的空白、key 順序、編碼），算出來的 bytes 就跟 LINE 當初簽的不一樣，HMAC 對不上 -> 403。

本 starter 的 `app/main.py` 是直接拿 `await request.body()` 的原始 bytes 去驗，沒有重序列化，這點是對的：

```python
body=await request.body()
if not verify_signature(body,x_line_signature): raise HTTPException(403,"Invalid LINE signature")
```

**怎麼修**：別在驗簽章前動 body。如果你前面架了 nginx / Cloudflare，確認它沒改 request body。本機要重現「正確 200、錯誤 403」可參考 `03-step-by-step.md` 的 `sig_demo.py`，輸出是 `[valid] 200 / [wrong] 403 / [missing] 403`。

## 2. 忘了設 secret，webhook 全部被擋（fail-closed）

**症狀**：切到真 AI provider 後，沒帶簽章或沒設 secret 的請求一律 403。

這是**刻意的**。`app/line.py`：沒 `LINE_CHANNEL_SECRET` 時，只有 `AI_PROVIDER=echo` 或 `LINE_ALLOW_INSECURE=1` 才放行，其餘回 False（-> 403）。本機重現（真實輸出）：

```
secret=(空), AI_PROVIDER=echo, LINE_ALLOW_INSECURE=None -> 200
secret=(空), AI_PROVIDER=http, LINE_ALLOW_INSECURE=None -> 403
secret=(空), AI_PROVIDER=http, LINE_ALLOW_INSECURE=1 -> 200
```

**怎麼修**：正式上線就把真的 `LINE_CHANNEL_SECRET` 設好。沒密鑰任何人都能偽造 LINE webhook 呼叫，所以這個 starter 預設不讓你裸奔。

## 3. 收得到 webhook，但使用者沒收到回覆（reply 401）

**症狀**：uvicorn 顯示 `POST /webhook/line ... 200 OK`，但 LINE 裡沒有任何回覆。

**原因**：回覆是另一個動作——`app/line.py` 的 `reply_text` 會打 `POST https://api.line.me/v2/bot/message/reply`，header 帶 `Authorization: Bearer <LINE_CHANNEL_ACCESS_TOKEN>`。如果 access token 沒設、設錯、或過期，LINE 會回 **401 Unauthorized**，回覆就送不出去。webhook 本身仍是 200，所以容易被忽略。

**怎麼修**：確認 `.env` 的 `LINE_CHANNEL_ACCESS_TOKEN` 是 console 裡按「發行」拿到的有效 token。注意 channel **secret** 和 channel **access token** 是兩個不同的值，別貼反。

## 4. ngrok 開了，但 LINE 還是沒打進來

**症狀**：本機 `curl /health` 正常、ngrok 也在跑，但傳訊息 bot 沒反應，ngrok / uvicorn 都沒看到 `POST /webhook/line`。

**常見原因**：

- LINE console 的 **Webhook URL** 沒設，或設成根網址漏了 `/webhook/line`（要是 `https://xxxx.ngrok-free.app/webhook/line`）。
- **Use webhook** 沒打開。
- 每次重開 ngrok 網址會變，但 console 還指著舊網址。
- ngrok 指到的 port 跟 uvicorn 不同（uvicorn 跑 8000 就要 `ngrok http 8000`）。

**怎麼修**：在 LINE console 用 **Verify** 按鈕測 webhook URL，會立刻告訴你連不連得到；換 ngrok 網址後記得回來更新。

## 5. replyToken 用過就失效

**症狀**：想對同一則訊息回第二次，或隔了很久才回，LINE 回錯誤。

**原因**：`replyToken` 只能用一次、且時效很短（約一分鐘內）。長時間任務不能靠 reply。

**怎麼修**：需要延遲或多次發送時，改用 push message API（`/v2/bot/message/push`，以 user id 為對象），不要重複用 replyToken。

## 6. 個資直送第三方 LLM

切到 `http` / `claude-cli` / `gemini-cli` provider 後，使用者打的字會原封不動送到外部 LLM。正式環境前先想清楚哪些內容能外送、要不要遮罩，必要時在 `app/ai.py` 加過濾。

## Debug 順序

1. 服務有沒有起來：`curl /health` 是不是 `{"ok":true}`。
2. webhook URL 對不對、Use webhook 有沒有開（console 的 Verify）。
3. 環境變數有沒有載入：secret 與 access token 是不是真的填了、沒貼反。
4. 用 `AI_PROVIDER=echo` 排除 AI 服務本身的問題。
5. 看完整錯誤，特別分清楚「webhook 200 但 reply 401」這種兩段式失敗。
6. 縮到最小可重現（像本文件的 `sig_demo.py`）。

## 問別人前準備好

- repo / branch
- 啟動指令
- 完整錯誤訊息（含是 webhook 端還是 reply 端）
- 你已經檢查過哪些設定
- secret / token 請遮掉，不要直接貼
