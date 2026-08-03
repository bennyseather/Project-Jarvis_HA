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
    maximum_segment_characters: int = 105
    generation_timeout: float = 30.0
    articulation_mode: str = "crisp"
    prewarm_text: str = "Systems ready."


class ChatterboxNanoEngine:
    """Keep one Nano model warm and run only one CPU synthesis at a time."""

    def __init__(self, config: ChatterboxConfig, *, model_factory=None) -> None:
        self.config = config
        self._model_factory = model_factory
        self._model = None
        self._lock = asyncio.Lock()
        self.ready = False
        self.conditioning_ready = False
        self.conditioning_seconds = 0.0
        self.warmup_seconds = 0.0
        self.last_error = ""
        self.last_first_audio_seconds = 0.0
        self.last_generation_seconds = 0.0

    async def warmup(self) -> None:
        async with self._lock:
            started = time.monotonic()
            await asyncio.to_thread(self._prepare_conditioning)
            if self.config.prewarm_text.strip():
                await asyncio.to_thread(
                    self._generate_waveform, self.config.prewarm_text.strip()
                )
            self.warmup_seconds = time.monotonic() - started
            LOGGER.info(
                "Chatterbox conditioning cached and model pre-warmed in %.2fs",
                self.warmup_seconds,
            )

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

        model = self._prepare_conditioning()
        waveform = self._generate_waveform(text)
        values = waveform.detach().cpu().float().numpy().reshape(-1)
        pcm = (np.clip(values, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()
        return pcm, int(model.sr)

    def _prepare_conditioning(self):
        """Load and condition the approved reference exactly once per process."""
        model = self._load()
        if self.conditioning_ready:
            return model
        reference = Path(self.config.reference_path)
        if not reference.is_file():
            raise FileNotFoundError(f"Jarvis reference not found: {reference}")
        started = time.monotonic()
        model.prepare_conditionals(str(reference), norm_loudness=False)
        self.conditioning_seconds = time.monotonic() - started
        self.conditioning_ready = True
        LOGGER.info(
            "Cached Chatterbox reference conditioning in %.2fs",
            self.conditioning_seconds,
        )
        return model

    def _generate_waveform(self, text: str):
        model = self._load()
        options = articulation_options(self.config.articulation_mode)
        return model.generate(text, **options)


def articulation_options(mode: str) -> dict[str, object]:
    """Return conservative Nano parameters favouring clear consonants."""
    if mode == "balanced":
        return {
            "temperature": 0.76,
            "top_p": 0.93,
            "repetition_penalty": 1.20,
        }
    return {
        "temperature": 0.66,
        "top_p": 0.90,
        "repetition_penalty": 1.26,
    }


def split_spoken_segments(text: str, maximum: int = 105) -> tuple[str, ...]:
    """Create articulate clause-sized segments without dropping words."""
    maximum = max(24, min(180, int(maximum)))
    normalized = " ".join(str(text).split())
    if not normalized:
        return ()
    sentences = _split_sentences(normalized)
    segments: list[str] = []
    for sentence in sentences:
        remaining = sentence.strip()
        while len(remaining) > maximum:
            cut = _natural_cut(remaining, maximum)
            if cut < 1:
                cut = maximum
            segments.append(remaining[:cut].strip())
            remaining = remaining[cut:].strip()
        if remaining:
            segments.append(remaining)
    return tuple(segments)


def _split_sentences(text: str) -> tuple[str, ...]:
    """Split terminal punctuation while protecting decimals and abbreviations."""
    protected = re.sub(r"(?<=\d)\.(?=\d)", "<DOT>", text)
    for abbreviation in ("Mr.", "Mrs.", "Dr.", "St.", "e.g.", "i.e."):
        protected = protected.replace(abbreviation, abbreviation.replace(".", "<DOT>"))
    parts = re.split(r"(?<=[.!?])\s+", protected)
    return tuple(part.replace("<DOT>", ".") for part in parts if part.strip())


def _natural_cut(text: str, maximum: int) -> int:
    """Prefer a substantial clause boundary, then fall back to a word boundary."""
    minimum = min(48, max(24, maximum // 2))
    window = text[: maximum + 1]
    candidates = [
        match.end()
        for match in re.finditer(r"[;:—–,]\s+", window)
        if match.end() >= minimum
    ]
    if candidates:
        return candidates[-1]
    cut = window.rfind(" ")
    return cut if cut >= minimum else maximum
