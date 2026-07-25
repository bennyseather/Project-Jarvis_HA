"""Small authenticated HTTP server for the local Home Assistant bridge."""
from __future__ import annotations
import asyncio
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread


class ConversationBridgeServer:
    def __init__(self, bridge, api_key: str, loop) -> None:
        self._bridge, self._api_key, self._loop = bridge, api_key, loop
        self._server = None

    def start(self, host="0.0.0.0", port=8099) -> None:
        outer = self
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                if self.path != "/v1/conversation" or self.headers.get("Authorization") != f"Bearer {outer._api_key}":
                    self.send_response(401); self.end_headers(); return
                try:
                    payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
                    result = asyncio.run_coroutine_threadsafe(outer._bridge.process(payload.get("text", ""), payload.get("confirmation_token")), outer._loop).result(timeout=60)
                    body = json.dumps(result).encode()
                    self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
                except Exception:
                    self.send_response(503); self.end_headers()
            def log_message(self, *args): pass
        self._server = ThreadingHTTPServer((host, port), Handler)
        Thread(target=self._server.serve_forever, daemon=True).start()

    def stop(self) -> None:
        if self._server: self._server.shutdown()
