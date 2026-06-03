#!/usr/bin/env python3
"""Parity smoke test for the LINE webhook surface shared by both implementations.

Spins a local fake LINE server, points the target app's Reply API at it via
LINE_API_BASE, drives the app through a proper signed webhook with Starlette's
TestClient, and asserts the captured reply. The SAME assertions pass against
app.main (hand-rolled) and app.main_sdk (line-bot-sdk), proving parity.

Target chosen by LINEBOT_SMOKE_TARGET (default: app.main). Exits non-zero on
any failure so CI can gate on it.
"""
import base64, hashlib, hmac, importlib, json, os, sys, threading
from http.server import BaseHTTPRequestHandler, HTTPServer

SECRET = "testsecret"
captured = []

class _Fake(BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        captured.append(json.loads(self.rfile.read(n).decode()))
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(json.dumps({"sentMessages": [{"id": "1", "quoteToken": "qt"}]}).encode())
    def log_message(self, *a): pass

srv = HTTPServer(("127.0.0.1", 0), _Fake)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()

# Env MUST be set before importing the target (config.py reads env at import).
os.environ.update(
    LINE_CHANNEL_SECRET=SECRET, LINE_CHANNEL_ACCESS_TOKEN="dummy",
    LINE_API_BASE=f"http://127.0.0.1:{port}", AI_PROVIDER="echo",
)
TARGET = os.getenv("LINEBOT_SMOKE_TARGET", "app.main")
mod = importlib.import_module(TARGET)
from starlette.testclient import TestClient
client = TestClient(mod.app)

def _event(text):
    return json.dumps({"destination": "U", "events": [{
        "type": "message", "mode": "active", "timestamp": 1700000000000,
        "source": {"type": "user", "userId": "U1"},
        "webhookEventId": "01H", "deliveryContext": {"isRedelivery": False},
        "replyToken": "RT", "message": {"id": "1", "type": "text", "text": text, "quoteToken": "q"},
    }]})

def _sign(body):
    return base64.b64encode(hmac.new(SECRET.encode(), body.encode(), hashlib.sha256).digest()).decode()

def _post(text, sig=None):
    captured.clear()
    body = _event(text)
    return client.post("/webhook/line", content=body,
                       headers={"X-Line-Signature": sig if sig is not None else _sign(body)})

failures = []
def check(cond, label):
    if not cond:
        failures.append(label)

try:
    r = _post("/ping")
    check(r.status_code == 200, "ping status 200")
    check(bool(captured) and captured[0]["messages"][0]["text"] == "pong", "ping -> pong")

    r = _post("營業時間")
    check(bool(captured) and captured[0]["messages"][0]["text"].startswith("我們的營業時間"), "keyword hours reply")

    r = _post("hello there")
    check(bool(captured) and captured[0]["messages"][0]["text"] == "LINE AI echo: hello there", "echo reply")

    r = _post("/ping", sig="invalidsignature")
    check(r.status_code == 403, "bad signature -> 403")
    check(not captured, "bad signature -> no reply sent")
finally:
    srv.shutdown()

if failures:
    print("FAIL:", "; ".join(failures), file=sys.stderr)
    sys.exit(1)
print(f"OK: parity checks passed (target={TARGET})")
