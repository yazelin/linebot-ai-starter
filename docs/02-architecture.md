# LINE Bot AI 入門模板：架構說明

## 核心檔案

- app/main.py：FastAPI webhook 入口與 LINE signature 驗證
- app/line.py：處理 LINE events、reply API
- app/ai.py：AI provider adapter，支援 echo / claude-cli / gemini-cli / HTTP API
- app/config.py：從 .env 載入 token 與模型設定

## 資料流

1. 使用者或 client 發出請求。
2. FastAPI / stdio 入口接收資料。
3. handler 解析訊息與設定。
4. adapter / tool / search 層執行實際工作。
5. 回傳最小可理解的結果。

## 設計原則

- 先讓流程可跑，再做漂亮抽象。
- token 與 secrets 全部放在環境變數。
- 每一層保持可以替換：入口、AI provider、資料來源、部署方式。
- 範例程式刻意保持小，方便你看懂後改成自己的版本。
