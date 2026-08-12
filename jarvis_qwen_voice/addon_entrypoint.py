"""Home Assistant entry point for the local CPU Qwen voice worker."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from qwen_engine import QwenConfig, QwenVoiceEngine
from server import serve


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


def load_config(path: Path = Path("/data/options.json")) -> QwenConfig:
    options = json.loads(path.read_text(encoding="utf-8"))
    legacy_segment_default = int(options.get("maximum_segment_characters", 180)) == 180
    legacy_cache_default = int(options.get("response_cache_entries", 24)) == 24
    return QwenConfig(
        reference_audio=str(options.get(
            "reference_audio", "/share/jarvis_voice/qwen-reference.wav"
        )),
        reference_text_file=str(options.get(
            "reference_text_file", "/share/jarvis_voice/qwen-reference.txt"
        )),
        cache_dir=str(options.get("model_cache_dir", "/data/models")),
        device="cpu",
        dtype="float32",
        cpu_threads=int(options.get("cpu_threads", 6)),
        maximum_segment_characters=int(
            240 if legacy_segment_default else options.get("maximum_segment_characters", 240)
        ),
        response_cache_entries=int(40 if legacy_cache_default else options.get("response_cache_entries", 40)),
        response_cache_dir=str(options.get("response_cache_dir", "/data/response-cache")),
    )


if __name__ == "__main__":
    asyncio.run(serve(load_config(), host="0.0.0.0", port=10400))
