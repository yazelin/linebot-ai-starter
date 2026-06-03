"""LINE Bot AI Starter — line-bot-sdk version. Run with:
    uvicorn app.main_sdk:app
Requires the `sdk` extra: uv sync --extra sdk."""
from fastapi import FastAPI, Request, Header
from .line_sdk import process_webhook

app = FastAPI(title="LINE Bot AI Starter (line-bot-sdk)")


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/webhook/line")
async def webhook(request: Request, x_line_signature: str = Header(default="")):
    await process_webhook(await request.body(), x_line_signature)
    return {"ok": True}
