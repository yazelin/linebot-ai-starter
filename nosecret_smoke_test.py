#!/usr/bin/env python3
"""Fail-closed parity check for the NO-channel-secret dev path.

When LINE_CHANNEL_SECRET is unset, both implementations must apply the same
policy (app/line.py:verify_signature and app/line_sdk.py:_dev_insecure_ok):
in AI_PROVIDER=echo (or LINE_ALLOW_INSECURE=1) they accept an UNSIGNED webhook
and still reply. This branch is re-implemented independently in each version,
so it gets its own parity test. The signed / bad-signature paths are covered by
parity_smoke_test.py.

Target chosen by LINEBOT_SMOKE_TARGET (default: app.main). Exits non-zero on
any failure so CI can gate on it.
"""
import importlib, json, os, sys, threading
from http.server import BaseHTTPRequestHandler, HTTPServer

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

# Crucial: NO channel secret, echo provider. Set before importing the target
# (config.py reads env at import). Clear any inherited secret explicitly.
os.environ.update(
    LINE_CHANNEL_SECRET="", LINE_CHANNEL_ACCESS_TOKEN="dummy",
    LINE_API_BASE=f"http://127.0.0.1:{port}", AI_PROVIDER="echo",
)
os.environ.pop("LINE_ALLOW_INSECURE", None)
TARGET = os.getenv("LINEBOT_SMOKE_TARGET", "app.main")
mod = importlib.import_module(TARGET)
from starlette.testclient import TestClient
client = TestClient(mod.app)

body = json.dumps({"destination": "U", "events": [{
    "type": "message", "mode": "active", "timestamp": 1700000000000,
    "source": {"type": "user", "userId": "U1"},
    "webhookEventId": "01H", "deliveryContext": {"isRedelivery": False},
    "replyToken": "RT", "message": {"id": "1", "type": "text", "text": "/ping", "quoteToken": "q"},
}]})

failures = []
def check(cond, label):
    if not cond:
        failures.append(label)

try:
    # No secret + echo: an UNSIGNED webhook (empty X-Line-Signature) is accepted.
    captured.clear()
    r = client.post("/webhook/line", content=body, headers={"X-Line-Signature": ""})
    check(r.status_code == 200, "no-secret echo: unsigned webhook accepted (200)")
    check(bool(captured) and captured[0]["messages"][0]["text"] == "pong",
          "no-secret echo: still replies (/ping -> pong)")
finally:
    srv.shutdown()

if failures:
    print("FAIL:", "; ".join(failures), file=sys.stderr)
    sys.exit(1)
print(f"OK: no-secret fail-closed (echo allow) check passed (target={TARGET})")
