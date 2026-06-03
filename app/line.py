import base64, hashlib, hmac, os, httpx
from .config import LINE_CHANNEL_SECRET, LINE_CHANNEL_ACCESS_TOKEN, AI_PROVIDER, LINE_API_BASE
from .bot import resolve_reply
def verify_signature(body, signature):
    # SECURITY: fail-closed by default.
    # If no channel secret is configured we cannot verify the LINE signature.
    # Accepting such requests would let anyone forge a webhook call, so we only
    # allow it through in an explicit local dev / echo context:
    #   - AI_PROVIDER == "echo"          (harmless echo bot, no real AI/secrets)
    #   - LINE_ALLOW_INSECURE == "1"     (operator explicitly opted in)
    if not LINE_CHANNEL_SECRET:
        if AI_PROVIDER == "echo" or os.getenv("LINE_ALLOW_INSECURE") == "1":
            return True
        return False
    expected=base64.b64encode(hmac.new(LINE_CHANNEL_SECRET.encode(),body,hashlib.sha256).digest()).decode()
    return hmac.compare_digest(expected, signature)
async def handle_events(payload):
    for e in payload.get("events",[]):
        if e.get("type")!="message" or e.get("message",{}).get("type")!="text": continue
        await reply_text(e["replyToken"], await resolve_reply(e["message"]["text"]))
async def reply_text(token,text):
    async with httpx.AsyncClient(timeout=30) as c:
        await c.post(LINE_API_BASE+"/v2/bot/message/reply",headers={"Authorization":"Bearer "+LINE_CHANNEL_ACCESS_TOKEN},json={"replyToken":token,"messages":[{"type":"text","text":text}]})
