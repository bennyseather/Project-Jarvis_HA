"""Lazy, serialized Chatterbox Nano CPU synthesis with sentence streaming."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
from pathlib import Path
import re
import time


LOGGER = logging.getLogger("jarvis_voice.chatterbox")


@dataclass(frozen=True)
class ChatterboxConfig:
    reference_path: str = "/app/jarvis-reference.wav"
    maximum_segment_characters: int = 180
    generation_timeout: float = 30.0


class ChatterboxNanoEngine:
    """Keep one Nano model warm and run only one CPU synthesis at a time."""

    def __init__(self, config: ChatterboxConfig, *, model_factory=None) -> None:
        self.config = config
        self._model_factory = model_factory
        self._model = None
        self._lock = asyncio.Lock()
        self.ready = False
        self.last_error = ""
        self.last_generation_seconds = 0.0

    async def warmup(self) -> None:
        async with self._lock:
            await asyncio.to_thread(self._load)

    async def synthesize_segments(self, text: str):
        async with self._lock:
            for segment in split_spoken_segments(
                text, self.config.maximum_segment_characters
            ):
                started = time.monotonic()
                try:
                    pcm, rate = await asyncio.wait_for(
                        asyncio.to_thread(self._synthesize_sync, segment),
                        self.config.generation_timeout,
                    )
                except Exception as error:
                    self.last_error = str(error)[:300]
                    raise
                self.last_generation_seconds = time.monotonic() - started
                yield pcm, rate, segment, self.last_generation_seconds

    def _load(self):
        if self._model is None:
            LOGGER.info("Loading Chatterbox Nano on CPU")
            if self._model_factory is not None:
                self._model = self._model_factory()
            else:
                from chatterbox.tts_turbo import ChatterboxTurboTTS
                self._model = ChatterboxTurboTTS.from_pretrained(
                    device="cpu", nano=True
                )
            self.ready = True
        return self._model

    def _synthesize_sync(self, text: str) -> tuple[bytes, int]:
        import numpy as np

        model = self._load()
        reference = Path(self.config.reference_path)
        options = {"audio_prompt_path": str(reference)} if reference.is_file() else {}
        waveform = model.generate(text, **options)
        values = waveform.detach().cpu().float().numpy().reshape(-1)
        pcm = (np.clip(values, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()
        return pcm, int(model.sr)


def split_spoken_segments(text: str, maximum: int = 180) -> tuple[str, ...]:
    """Create bounded natural segments without dropping any words."""
    normalized = " ".join(str(text).split())
    if not normalized:
        return ()
    sentences = re.split(r"(?<=[.!?])\s+", normalized)
    segments: list[str] = []
    for sentence in sentences:
        remaining = sentence.strip()
        while len(remaining) > maximum:
            cut = remaining.rfind(" ", 0, maximum + 1)
            if cut < 1:
                cut = maximum
            segments.append(remaining[:cut].strip())
            remaining = remaining[cut:].strip()
        if remaining:
            segments.append(remaining)
    return tuple(segments)
