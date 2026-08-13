"""Project Jarvis private Nest/go2rtc camera bridge."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import signal
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlencode

from aiohttp import ClientSession, ClientTimeout, web

LOGGER = logging.getLogger("jarvis_camera_bridge")
OPTIONS = Path("/data/options.json")
GO2RTC_CONFIG = Path("/data/go2rtc.yaml")
CACHE_DIR = Path("/data/snapshots")
GO2RTC_API = "http://127.0.0.1:1984"


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "camera"


@dataclass
class CameraRuntime:
    name: str
    slug: str
    device_id: str
    interval: int
    last_success: float = 0.0
    last_attempt: float = 0.0
    last_error: str = ""
    failures: int = 0
    cooldown_until: float = 0.0
    connected: bool = False
    active_viewers: int = 0
    snapshot: Path = field(default_factory=Path)


class Bridge:
    def __init__(self, options: dict) -> None:
        self.options = options
        self.token = str(options["bridge_token"])
        self.stale_after = int(options.get("stale_after", 60))
        default_interval = int(options.get("snapshot_interval", 15))
        self.cameras = {
            slugify(item["name"]): CameraRuntime(
                name=item["name"],
                slug=slugify(item["name"]),
                device_id=item["device_id"],
                interval=max(10, min(60, int(item.get("snapshot_interval", default_interval)))),
                snapshot=CACHE_DIR / f"{slugify(item['name'])}.jpg",
            )
            for item in options.get("cameras", [])
        }
        self.session: ClientSession | None = None
        self.go2rtc: asyncio.subprocess.Process | None = None
        self.started = time.time()

    def write_go2rtc_config(self) -> None:
        required = ("project_id", "client_id", "client_secret", "refresh_token")
        missing = [key for key in required if not self.options.get(key)]
        if missing:
            raise RuntimeError(f"Missing Nest credentials: {', '.join(missing)}")
        lines = ["api:", "  listen: 127.0.0.1:1984", "rtsp:", "  listen: :8554", "streams:"]
        preload = []
        for camera in self.cameras.values():
            query = urlencode(
                {
                    "project_id": self.options["project_id"],
                    "client_id": self.options["client_id"],
                    "client_secret": self.options["client_secret"],
                    "refresh_token": self.options["refresh_token"],
                    "device_id": camera.device_id,
                }
            )
            lines.extend((f"  {camera.slug}:", f"    - nest:?{query}"))
            preload.append(camera.slug)
        if preload:
            lines.append("preload:")
            lines.extend(f"  {slug}:" for slug in preload)
        GO2RTC_CONFIG.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.chmod(GO2RTC_CONFIG, 0o600)

    async def start(self) -> None:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self.write_go2rtc_config()
        self.session = ClientSession(timeout=ClientTimeout(total=20))
        self.go2rtc = await asyncio.create_subprocess_exec(
            "/usr/local/bin/go2rtc", "-config", str(GO2RTC_CONFIG)
        )
        await asyncio.sleep(2)
        for camera in self.cameras.values():
            asyncio.create_task(self.snapshot_loop(camera))

    async def close(self) -> None:
        if self.session:
            await self.session.close()
        if self.go2rtc and self.go2rtc.returncode is None:
            self.go2rtc.send_signal(signal.SIGTERM)
            await self.go2rtc.wait()

    async def snapshot_loop(self, camera: CameraRuntime) -> None:
        while True:
            delay = max(0.0, camera.cooldown_until - time.time())
            if delay:
                await asyncio.sleep(delay)
            camera.last_attempt = time.time()
            try:
                assert self.session
                async with self.session.get(
                    f"{GO2RTC_API}/api/frame.jpeg",
                    params={"src": camera.slug, "cache": f"{camera.interval}s"},
                ) as response:
                    if response.status == 429:
                        raise RuntimeError("Nest/go2rtc rate limited (429)")
                    response.raise_for_status()
                    image = await response.read()
                    if len(image) < 1024:
                        raise RuntimeError("Snapshot response was unexpectedly small")
                    temp = camera.snapshot.with_suffix(".tmp")
                    temp.write_bytes(image)
                    temp.replace(camera.snapshot)
                camera.last_success = time.time()
                camera.last_error = ""
                camera.failures = 0
                camera.cooldown_until = 0
                camera.connected = True
            except Exception as err:  # retain the last good frame
                camera.failures += 1
                camera.connected = False
                camera.last_error = str(err)[:240]
                backoff = min(300, 5 * (2 ** min(camera.failures - 1, 6)))
                camera.cooldown_until = time.time() + backoff
                LOGGER.warning("Snapshot failed for %s; retry in %ss: %s", camera.slug, backoff, err)
            await asyncio.sleep(camera.interval)

    async def refresh_viewers(self) -> None:
        if not self.session:
            return
        for camera in self.cameras.values():
            try:
                async with self.session.get(f"{GO2RTC_API}/api/streams", params={"src": camera.slug}) as response:
                    payload = await response.json()
                stream = payload.get(camera.slug, payload) if isinstance(payload, dict) else {}
                consumers = stream.get("consumers", []) if isinstance(stream, dict) else []
                camera.active_viewers = max(0, len(consumers) - 1)  # discount preload
            except Exception:
                camera.active_viewers = 0

    def status(self) -> dict:
        now = time.time()
        process_online = bool(self.go2rtc and self.go2rtc.returncode is None)
        cameras = []
        for camera in self.cameras.values():
            age = round(now - camera.last_success, 1) if camera.last_success else None
            cameras.append(
                {
                    "id": camera.slug,
                    "name": camera.name,
                    "connected": camera.connected,
                    "snapshot_available": camera.snapshot.exists(),
                    "snapshot_age_seconds": age,
                    "snapshot_stale": age is None or age > self.stale_after,
                    "last_success": camera.last_success or None,
                    "last_error": camera.last_error,
                    "cooldown_seconds": max(0, round(camera.cooldown_until - now)),
                    "active_viewers": camera.active_viewers,
                    "rtsp_path": f"/{camera.slug}",
                }
            )
        return {"online": process_online, "uptime_seconds": round(now - self.started), "cameras": cameras}


@web.middleware
async def auth_middleware(request: web.Request, handler):
    bridge: Bridge = request.app["bridge"]
    if request.headers.get("Authorization") != f"Bearer {bridge.token}":
        raise web.HTTPUnauthorized()
    return await handler(request)


async def status_handler(request: web.Request) -> web.Response:
    bridge: Bridge = request.app["bridge"]
    await bridge.refresh_viewers()
    return web.json_response(bridge.status())


async def snapshot_handler(request: web.Request) -> web.Response:
    bridge: Bridge = request.app["bridge"]
    camera = bridge.cameras.get(request.match_info["camera_id"])
    if not camera or not camera.snapshot.exists():
        raise web.HTTPNotFound(text="No cached snapshot is available yet")
    return web.FileResponse(camera.snapshot, headers={"Cache-Control": "no-store"})


async def create_app() -> web.Application:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    options = json.loads(OPTIONS.read_text(encoding="utf-8"))
    bridge = Bridge(options)
    await bridge.start()
    app = web.Application(middlewares=[auth_middleware])
    app["bridge"] = bridge
    app.router.add_get("/v1/status", status_handler)
    app.router.add_get("/v1/cameras/{camera_id}/snapshot.jpg", snapshot_handler)
    app.on_cleanup.append(lambda _: bridge.close())
    return app


web.run_app(create_app(), host="0.0.0.0", port=10500)
