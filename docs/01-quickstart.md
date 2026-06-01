# LINE Bot AI 入門模板：快速開始

## 前置需求

- Python 3.10+
- Git
- 可以使用終端機
- 如果要接真實 AI 或平台 token，請準備對應帳號與 API key。

## 最短路徑

1. 建立 LINE Messaging API channel
2. 設定 LINE_CHANNEL_SECRET 與 LINE_CHANNEL_ACCESS_TOKEN
3. 本機啟動 FastAPI
4. 把公開 HTTPS URL 填到 LINE webhook

## 安裝與啟動

```bash
git clone https://github.com/yazelin/linebot-ai-starter.git
cd linebot-ai-starter
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# 編輯 .env：LINE_CHANNEL_SECRET、LINE_CHANNEL_ACCESS_TOKEN、AI_PROVIDER
uvicorn app.main:app --reload --port 8000
```

## 健康檢查

```bash
curl http://127.0.0.1:8000/health
```

## 常用入口

- GET /health：健康檢查
- POST /webhook/line：LINE Messaging API webhook

## 第一次成功的標準

- 服務能啟動
- 基本 endpoint 有回應
- 範例流程能跑通
- 秘密 token 沒有 commit 到 GitHub
