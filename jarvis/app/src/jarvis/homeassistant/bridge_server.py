"""Small authenticated HTTP server for the local Home Assistant bridge."""
from __future__ import annotations
import asyncio
import json
from urllib.parse import urlparse, parse_qs
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread


class ConversationBridgeServer:
    def __init__(self, bridge, api_key: str, loop) -> None:
        self._bridge, self._api_key, self._loop = bridge, api_key, loop
        self._server = None

    async def _learning_snapshot(self):
        # SQLite belongs to the application loop, not the HTTP worker thread.
        # A monitoring GET must not update stored routine statuses.
        return self._bridge._application.container.contextual_routines.insights(refresh=False)

    async def _household_snapshot(self):
        from jarvis.household_overview import overview
        from jarvis.household_planner import get_planner
        container=self._bridge._application.container
        payload=overview(container.household_profile)
        if getattr(container,'home_assistant',None) is not None:
            payload['planner']=get_planner(container).project()
        return payload

    async def _planner_request(self,payload):
        from jarvis.household_planner import get_planner
        if not isinstance(payload,dict) or set(payload)!={'action','payload','owner'}:raise ValueError('Invalid planner request')
        try:
            result=await get_planner(self._bridge._application.container).request(payload['action'],payload['payload'],payload['owner'])
            return {'schema_version':1,'ok':True,'result':result}
        except ValueError as error:return {'schema_version':1,'ok':False,'error':str(error)}

    def start(self, host="0.0.0.0", port=8099) -> None:
        outer = self
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.headers.get("Authorization") != f"Bearer {outer._api_key}":
                    self.send_response(401); self.end_headers(); return
                try:
                    if self.path == "/v1/household":
                        from jarvis.household_overview import overview
                        payload = (asyncio.run_coroutine_threadsafe(outer._household_snapshot(),outer._loop).result(timeout=8)
                            if outer._loop is not None else overview(getattr(outer._bridge._application.container, "household_profile", None)))
                    elif self.path == "/v1/learning":
                        future = asyncio.run_coroutine_threadsafe(outer._learning_snapshot(), outer._loop)
                        try:
                            payload = future.result(timeout=5)
                        except TimeoutError:
                            future.cancel()
                            raise
                    elif self.path == "/v1/orchestration":
                        payload = outer._bridge._application.container.efficient_intelligence.metrics()
                    elif urlparse(self.path).path == "/v1/voice/turn":
                        controller = outer._bridge._voice_turns
                        request_id = parse_qs(urlparse(self.path).query).get("request_id", [""])[0]
                        payload = (asyncio.run_coroutine_threadsafe(
                            controller.inspect(request_id), outer._loop).result(timeout=5)
                            if controller else {"state": "not_started"})
                    else:
                        self.send_response(404); self.end_headers(); return
                    body = json.dumps(payload).encode()
                    self.send_response(200); self.send_header("Cache-Control", "no-store"); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
                except Exception:
                    self.send_response(503); self.end_headers()
            def do_POST(self):
                if self.path=='/v1/planner':
                    if self.headers.get('Authorization')!=f'Bearer {outer._api_key}':self.send_response(401);self.end_headers();return
                    try:
                        length=int(self.headers.get('Content-Length','0'))
                        if not 0<length<=8192:raise ValueError('Invalid request size')
                        from jarvis.calendar_membership import unique_json
                        payload=unique_json(self.rfile.read(length).decode('utf-8'))
                        future=asyncio.run_coroutine_threadsafe(outer._planner_request(payload),outer._loop)
                        try:result=future.result(timeout=32)
                        except TimeoutError:future.cancel();raise
                        body=json.dumps(result).encode()
                        self.send_response(200);self.send_header('Cache-Control','no-store');self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
                    except Exception:self.send_response(503);self.end_headers()
                    return
                if self.path != "/v1/conversation" or self.headers.get("Authorization") != f"Bearer {outer._api_key}":
                    self.send_response(401); self.end_headers(); return
                try:
                    payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
                    result = asyncio.run_coroutine_threadsafe(
                        outer._bridge.process(
                            payload.get("text", ""),
                            payload.get("confirmation_token"),
                            payload.get("conversation_id"),
                            bool(payload.get("voice_mode", False)),
                            payload.get("proactive_voice_route"),
                            payload.get("source_id"),
                            payload.get("activation_id"),
                            speaker_context=payload.get("speaker_context"),
                        ),
                        outer._loop,
                    ).result(timeout=60)
                    body = json.dumps(result).encode()
                    self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
                except Exception:
                    self.send_response(503); self.end_headers()
            def log_message(self, *args): pass
        self._server = ThreadingHTTPServer((host, port), Handler)
        Thread(target=self._server.serve_forever, daemon=True).start()

    def stop(self) -> None:
        if self._server: self._server.shutdown()
