"""Warm, serialized Qwen3-TTS voice cloning with cached conditioning."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
import re
import time


@dataclass(frozen=True)
class QwenConfig:
    model: str = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"
    reference_audio: str = "/data/reference.wav"
    reference_text_file: str = "/data/reference.txt"
    cache_dir: str = "/data/models"
    device: str = "cuda:0"
    dtype: str = "bfloat16"
    cpu_threads: int = 6
    maximum_segment_characters: int = 180


class QwenVoiceEngine:
    def __init__(self, config: QwenConfig, *, model_factory=None) -> None:
        self.config = config
        self._model_factory = model_factory
        self._model = None
        self._prompt = None
        self._lock = asyncio.Lock()
        self.ready = False
        self.last_error = ""
        self.model_load_seconds = 0.0
        self.prompt_encode_seconds = 0.0
        self.last_generation_seconds = 0.0
        self.last_first_audio_seconds = 0.0

    async def warmup(self) -> None:
        async with self._lock:
            await asyncio.to_thread(self._prepare_sync)

    async def synthesize_segments(self, text: str):
        async with self._lock:
            request_started = time.monotonic()
            for index, segment in enumerate(split_segments(
                text, self.config.maximum_segment_characters
            )):
                started = time.monotonic()
                try:
                    pcm, rate = await asyncio.to_thread(self._generate_sync, segment)
                except Exception as error:
                    self.last_error = str(error)[:300]
                    raise
                self.last_generation_seconds = time.monotonic() - started
                if index == 0:
                    self.last_first_audio_seconds = time.monotonic() - request_started
                yield pcm, rate, segment, self.last_generation_seconds

    def _prepare_sync(self) -> None:
        reference = Path(self.config.reference_audio)
        transcript = Path(self.config.reference_text_file)
        if not reference.is_file():
            raise FileNotFoundError(f"Private reference audio not found: {reference}")
        if not transcript.is_file():
            raise FileNotFoundError(f"Private reference transcript not found: {transcript}")
        reference_text = transcript.read_text(encoding="utf-8").strip()
        if not reference_text:
            raise ValueError("Private reference transcript is empty")
        if self._model is None:
            started = time.monotonic()
            if self._model_factory is not None:
                self._model = self._model_factory()
            else:
                import torch
                from huggingface_hub import snapshot_download
                from qwen_tts import Qwen3TTSModel
                if self.config.device == "cpu":
                    torch.set_num_threads(max(1, int(self.config.cpu_threads)))
                    torch.set_num_interop_threads(1)
                dtype = {
                    "float32": torch.float32,
                    "bfloat16": torch.bfloat16,
                    "float16": torch.float16,
                }.get(self.config.dtype)
                if dtype is None:
                    raise ValueError(f"Unsupported Qwen dtype: {self.config.dtype}")
                # Transformers may otherwise download only the root model files
                # before resolving the nested speech tokenizer as a local path.
                # Materialize and validate the complete repository snapshot first.
                model_path = Path(snapshot_download(
                    repo_id=self.config.model,
                    cache_dir=self.config.cache_dir,
                ))
                required = model_path / "speech_tokenizer" / "preprocessor_config.json"
                if not required.is_file():
                    raise FileNotFoundError(
                        "Qwen model snapshot is incomplete; missing "
                        f"{required}. Restart the add-on to retry the download."
                    )
                self._model = Qwen3TTSModel.from_pretrained(
                    str(model_path),
                    device_map=self.config.device,
                    dtype=dtype,
                    attn_implementation="sdpa",
                    cache_dir=self.config.cache_dir,
                )
            self.model_load_seconds = time.monotonic() - started
        if self._prompt is None:
            started = time.monotonic()
            self._prompt = self._model.create_voice_clone_prompt(
                ref_audio=str(reference),
                ref_text=reference_text,
                x_vector_only_mode=False,
            )
            self.prompt_encode_seconds = time.monotonic() - started
        self.ready = True

    def _generate_sync(self, text: str) -> tuple[bytes, int]:
        import numpy as np

        self._prepare_sync()
        waveforms, rate = self._model.generate_voice_clone(
            text=text,
            language="English",
            voice_clone_prompt=self._prompt,
        )
        values = np.asarray(waveforms[0], dtype=np.float32).reshape(-1)
        pcm = (np.clip(values, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()
        return pcm, int(rate)


def split_segments(text: str, maximum: int = 180) -> tuple[str, ...]:
    """Split long replies at sentence boundaries without losing content."""
    normalized = " ".join(str(text).split())
    if not normalized:
        return ()
    maximum = max(60, min(300, int(maximum)))
    protected = re.sub(r"(?<=\d)\.(?=\d)", "<DOT>", normalized)
    sentences = [
        part.replace("<DOT>", ".")
        for part in re.split(r"(?<=[.!?])\s+", protected)
        if part.strip()
    ]
    output: list[str] = []
    for sentence in sentences:
        remaining = sentence.strip()
        while len(remaining) > maximum:
            cut = remaining.rfind(" ", 0, maximum + 1)
            if cut < maximum // 2:
                cut = maximum
            output.append(remaining[:cut].strip())
            remaining = remaining[cut:].strip()
        if remaining:
            output.append(remaining)
    return tuple(output)
