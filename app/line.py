import base64, hashlib, hmac, httpx
from .config import LINE_CHANNEL_SECRET, LINE_CHANNEL_ACCESS_TOKEN
from .ai import ask_ai
def verify_signature(body, signature):
    if not LINE_CHANNEL_SECRET: return True
    expected=base64.b64encode(hmac.new(LINE_CHANNEL_SECRET.encode(),body,hashlib.sha256).digest()).decode()
    return hmac.compare_digest(expected, signature)
async def handle_events(payload):
    for e in payload.get("events",[]):
        if e.get("type")!="message" or e.get("message",{}).get("type")!="text": continue
        text=e["message"]["text"]; reply="pong" if text=="/ping" else await ask_ai(text)
        await reply_text(e["replyToken"], reply[:4500])
async def reply_text(token,text):
    async with httpx.AsyncClient(timeout=30) as c: await c.post("https://api.line.me/v2/bot/message/reply",headers={"Authorization":"Bearer "+LINE_CHANNEL_ACCESS_TOKEN},json={"replyToken":token,"messages":[{"type":"text","text":text}]})
