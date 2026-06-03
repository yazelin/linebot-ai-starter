"""Shared bot reply logic — used by BOTH the hand-rolled (app/line.py) and the
line-bot-sdk (app/line_sdk.py) implementations, so the two behave identically."""
from .ai import ask_ai

# 關鍵字自動回覆表：訊息文字完全相符時，直接回固定字串，不經過 AI。
KEYWORD_REPLIES = {
    "/ping": "pong",
    "營業時間": "我們的營業時間是週一到週五 09:00-18:00。",
}


async def resolve_reply(text: str) -> str:
    """Resolve an incoming text message to a reply string (keyword table first,
    otherwise the AI provider), truncated to LINE's practical length limit."""
    reply = KEYWORD_REPLIES[text] if text in KEYWORD_REPLIES else await ask_ai(text)
    return reply[:4500]
