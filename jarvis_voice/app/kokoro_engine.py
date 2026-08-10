"""Lazy, CPU-only Kokoro synthesis for the Jarvis Wyoming service."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging


LOGGER = logging.getLogger("jarvis_voice.kokoro")
SUPPORTED_VOICES = ("bm_george", "bm_fable", "bm_daniel", "bm_lewis")


@dataclass(frozen=True)
class KokoroConfig:
    voice: str = "bm_george"
    speed: float = 0.94
    model_path: str = "/app/kokoro-v1.0.onnx"
    voices_path: str = "/app/voices-v1.0.bin"


class KokoroEngine:
    def __init__(self, config: KokoroConfig) -> None:
        if config.voice not in SUPPORTED_VOICES:
            raise ValueError(f"Unsupported Kokoro voice: {config.voice}")
        self.config = config
        self._model = None
        self._lock = asyncio.Lock()

    async def synthesize(self, text: str, voice: str | None = None) -> tuple[bytes, int]:
        selected = voice if voice in SUPPORTED_VOICES else self.config.voice
        async with self._lock:
            return await asyncio.to_thread(self._synthesize_sync, text, selected)

    def _synthesize_sync(self, text: str, voice: str) -> tuple[bytes, int]:
        import numpy as np
        if self._model is None:
            from kokoro_onnx import Kokoro
            LOGGER.info("Loading local Kokoro model")
            self._model = Kokoro(self.config.model_path, self.config.voices_path)
        samples, rate = self._model.create(
            text, voice=voice, speed=self.config.speed, lang="en-gb"
        )
        pcm = (np.clip(samples, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()
        return pcm, int(rate)
