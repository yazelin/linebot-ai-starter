"""line-bot-sdk v3 implementation of the same three LINE concerns the hand-rolled
app/line.py does: signature verification, event parsing, and the Reply API.
Reuses app/bot.py:resolve_reply so behavior matches the hand-rolled version.
Requires the `sdk` extra: uv sync --extra sdk."""
import json, os
from fastapi import HTTPException
from .config import LINE_CHANNEL_SECRET, LINE_CHANNEL_ACCESS_TOKEN, AI_PROVIDER, LINE_API_BASE
from .bot import resolve_reply
from linebot.v3 import WebhookParser
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.messaging import (
    Configuration, AsyncApiClient, AsyncMessagingApi, ReplyMessageRequest, TextMessage,
    QuickReply, QuickReplyItem, MessageAction,
)

_parser = WebhookParser(LINE_CHANNEL_SECRET) if LINE_CHANNEL_SECRET else None


def _dev_insecure_ok() -> bool:
    # Mirror app/line.py's fail-closed policy for the no-secret case.
    return AI_PROVIDER == "echo" or os.getenv("LINE_ALLOW_INSECURE") == "1"


def _extract_events(body: str, signature: str):
    """Return a list of (text, reply_token). Raises HTTPException(403) on a bad
    or unverifiable signature, matching the hand-rolled behavior."""
    if _parser is None:
        if not _dev_insecure_ok():
            raise HTTPException(403, "Invalid LINE signature")
        return [(e["message"]["text"], e["replyToken"])
                for e in json.loads(body).get("events", [])
                if e.get("type") == "message" and e.get("message", {}).get("type") == "text"]
    try:
        parsed = _parser.parse(body, signature)
    except InvalidSignatureError:
        raise HTTPException(403, "Invalid LINE signature")
    return [(ev.message.text, ev.reply_token) for ev in parsed
            if isinstance(ev, MessageEvent) and isinstance(ev.message, TextMessageContent)]


# BONUS (SDK-only): a typed Quick Reply. Hand-rolling this means assembling the
# nested quickReply JSON by hand; the SDK builds it from typed objects in a few
# lines. This is an awareness example of what the framework gives you for free.
_BONUS_KEYWORD = "選單"

def _quick_reply_message() -> TextMessage:
    return TextMessage(
        text="請選擇:",
        quick_reply=QuickReply(items=[
            QuickReplyItem(action=MessageAction(label="營業時間", text="營業時間")),
            QuickReplyItem(action=MessageAction(label="Ping", text="/ping")),
        ]),
    )


async def process_webhook(raw_body: bytes, signature: str) -> None:
    events = _extract_events(raw_body.decode(), signature)
    if not events:
        return
    config = Configuration(host=LINE_API_BASE, access_token=LINE_CHANNEL_ACCESS_TOKEN or "dummy")
    async with AsyncApiClient(config) as api_client:
        api = AsyncMessagingApi(api_client)
        for text, token in events:
            if text == _BONUS_KEYWORD:
                message = _quick_reply_message()
            else:
                message = TextMessage(text=await resolve_reply(text))
            await api.reply_message(ReplyMessageRequest(reply_token=token, messages=[message]))
