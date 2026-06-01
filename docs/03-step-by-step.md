# LINE Bot AI 入門模板：完整操作流程

## 步驟

1. 先用 AI_PROVIDER=echo 測試 webhook 能收到 LINE 訊息。
2. 確認 LINE Developers 後台 webhook URL 是 https://你的網域/webhook/line。
3. 確認 Use webhook 開啟，Auto-reply 關閉或避免干擾測試。
4. 測試 /ping，確定 reply API 可回覆。
5. 改成 HTTP LLM 或 CLI provider。
6. 依情境加上表單、訂單、FAQ 或內部通知流程。

## 建議紀錄

- 你使用的 Python 版本
- 啟動指令
- `.env` 裡有哪些 key 已設定；不要貼出 secret 值
- webhook / endpoint URL
- 錯誤訊息完整內容
- 你預期發生什麼、實際發生什麼

## 下一個里程碑

完成最小流程後，不要急著加功能。先找一個真實情境，讓這個 starter 解決一個很小但明確的問題。
