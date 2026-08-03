"""Home Assistant add-on entry point for the local Jarvis voice processor."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from server import VoiceProxyConfig, run_server


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


def load_config(path: Path = Path("/data/options.json")) -> VoiceProxyConfig:
    options = json.loads(path.read_text(encoding="utf-8"))
    return VoiceProxyConfig(
        upstream_host=str(options.get("upstream_host", "core-piper")),
        upstream_port=int(options.get("upstream_port", 10200)),
        profile=str(options.get("profile", "refined")),
        strength=float(options.get("strength", 0.65)),
        output_gain=float(options.get("output_gain", 0.92)),
        voice=str(options.get("voice", "bm_george")),
        speed=float(options.get("speed", 0.94)),
        piper_fallback=bool(options.get("piper_fallback", True)),
    )


if __name__ == "__main__":
    asyncio.run(run_server(load_config()))
