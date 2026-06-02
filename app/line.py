import base64, hashlib, hmac, os, httpx
from .config import LINE_CHANNEL_SECRET, LINE_CHANNEL_ACCESS_TOKEN, AI_PROVIDER
from .ai import ask_ai
def verify_signature(body, signature):
    # SECURITY: fail-closed by default.
    # If no channel secret is configured we cannot verify the LINE signature.
    # Accepting such requests would let anyone forge a webhook call, so we only
    # allow it through in an explicit local dev / echo context:
    #   - AI_PROVIDER == "echo"          (harmless echo bot, no real AI/secrets)
    #   - LINE_ALLOW_INSECURE == "1"     (operator explicitly opted in)
    # In any real provider mode without a secret we REJECT (return False).
    if not LINE_CHANNEL_SECRET:
        if AI_PROVIDER == "echo" or os.getenv("LINE_ALLOW_INSECURE") == "1":
            return True
        return False
    expected=base64.b64encode(hmac.new(LINE_CHANNEL_SECRET.encode(),body,hashlib.sha256).digest()).decode()
    return hmac.compare_digest(expected, signature)
# 關鍵字自動回覆表：訊息文字完全相符時，直接回固定字串，不經過 AI。
# 想加新關鍵字，就在這裡多一行 key: value。
KEYWORD_REPLIES = {
    "/ping": "pong",
    "營業時間": "我們的營業時間是週一到週五 09:00-18:00。",
}
async def handle_events(payload):
    for e in payload.get("events",[]):
        if e.get("type")!="message" or e.get("message",{}).get("type")!="text": continue
        text=e["message"]["text"]
        # 先比對關鍵字表；沒命中才交給 AI provider。
        reply=KEYWORD_REPLIES[text] if text in KEYWORD_REPLIES else await ask_ai(text)
        await reply_text(e["replyToken"], reply[:4500])
async def reply_text(token,text):
    async with httpx.AsyncClient(timeout=30) as c: await c.post("https://api.line.me/v2/bot/message/reply",headers={"Authorization":"Bearer "+LINE_CHANNEL_ACCESS_TOKEN},json={"replyToken":token,"messages":[{"type":"text","text":text}]})
