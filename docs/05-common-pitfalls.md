# LINE Bot AI 入門模板：常見問題與踩雷清單

## 常見坑

- LINE signature 驗證失敗通常是 channel secret 錯、body 被 proxy 改掉、或 webhook URL 指到錯服務。
- LINE replyToken 只能用一次且有效時間短，長任務要改用 push message。
- 沒有 LINE_CHANNEL_ACCESS_TOKEN 時，程式可以收 webhook 但無法回覆。
- 本機測試 webhook 需要 HTTPS tunnel，例如 Cloudflare Tunnel 或 ngrok。
- 正式環境要避免把使用者個資直接送到第三方 LLM。

## Debug 順序

1. 先確認服務有沒有啟動。
2. 再確認 endpoint / webhook URL 是否正確。
3. 檢查環境變數是否有載入。
4. 用 echo / fake provider 排除 AI 服務問題。
5. 查看完整錯誤訊息，不要只看最後一行。
6. 把問題縮到最小可重現案例。

## 問別人前準備

- repo / branch
- 啟動指令
- 完整錯誤訊息
- 你已經檢查過哪些設定
- secret 請遮掉，不要直接貼 token
