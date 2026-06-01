![Brand banner](assets/banner.svg)

# LINE Bot AI Starter

A minimal LINE Messaging API bot with AI provider adapters.

## 繁中定位

**LINE Bot AI 入門模板** 面向台灣繁中受眾。

- 主要受眾：適合想用 LINE 做客服、訂單、點餐、內部通知或群組助理的台灣團隊。
- 核心承諾：把 LINE 官方帳號或群組變成可接 AI、可接資料、可部署的工作流入口。
- CTA 頁：https://yazelin.github.io/linebot-ai-starter/



## 公開教學文件

這個 repo 的教學內容直接公開，讓你可以先自己照著跑；如果需要手把手 debug、改成你的公司或個人場景，再考慮工作坊或顧問協助。

- 網頁版教學：https://yazelin.github.io/linebot-ai-starter/tutorial.html
- Markdown 教學：[`docs/`](docs/)
- 快速開始：[`docs/01-quickstart.md`](docs/01-quickstart.md)
- 常見踩雷：[`docs/05-common-pitfalls.md`](docs/05-common-pitfalls.md)

## Who this is for

Teams in Taiwan/Japan that want LINE-based AI workflow assistants.

## Features

- FastAPI LINE webhook
- Signature verification
- Echo / Claude CLI / Gemini CLI / HTTP providers
- Docker-ready

## Quick start

```bash
git clone https://github.com/yazelin/linebot-ai-starter.git
cd linebot-ai-starter
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt  # if present
```

See the source files and `.env.example` for the minimal runnable path.

## Learn / get help

This repo is also a CTA page for workshops and consulting:

- GitHub Pages: https://yazelin.github.io/linebot-ai-starter/
- Contact: yaze.lin.j303@gmail.com

## License

MIT


## Brand / CTA design

- Landing page: https://yazelin.github.io/linebot-ai-starter/
- CI spec: [DESIGN.md](DESIGN.md)
- Banner: [assets/banner.svg](assets/banner.svg)
- Logo: [assets/logo.svg](assets/logo.svg)
