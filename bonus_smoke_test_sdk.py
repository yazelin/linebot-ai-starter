#!/usr/bin/env python3
"""Bonus check for the SDK-only Quick Reply rich message. The hand-rolled app
has no equivalent, so this runs only against app.main_sdk (CI's sdk track)."""
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

os.environ.update(
    LINE_CHANNEL_SECRET=SECRET, LINE_CHANNEL_ACCESS_TOKEN="dummy",
    LINE_API_BASE=f"http://127.0.0.1:{port}", AI_PROVIDER="echo",
)
mod = importlib.import_module("app.main_sdk")
from starlette.testclient import TestClient
client = TestClient(mod.app)

body = json.dumps({"destination": "U", "events": [{
    "type": "message", "mode": "active", "timestamp": 1700000000000,
    "source": {"type": "user", "userId": "U1"},
    "webhookEventId": "01H", "deliveryContext": {"isRedelivery": False},
    "replyToken": "RT", "message": {"id": "1", "type": "text", "text": "選單", "quoteToken": "q"},
}]})
sig = base64.b64encode(hmac.new(SECRET.encode(), body.encode(), hashlib.sha256).digest()).decode()

failures = []
try:
    client.post("/webhook/line", content=body, headers={"X-Line-Signature": sig})
    msg = captured[0]["messages"][0] if captured else {}
    if "quickReply" not in msg:
        failures.append(f"expected quickReply in reply message, got keys {list(msg)}")
    else:
        items = msg["quickReply"].get("items", [])
        if not items:
            failures.append("quickReply has no items")
finally:
    srv.shutdown()

if failures:
    print("FAIL:", "; ".join(failures), file=sys.stderr)
    sys.exit(1)
print("OK: SDK Quick Reply bonus check passed")
