"""Standalone private CosyVoice 3 Wyoming streaming worker."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time

from cosyvoice_engine import CosyVoiceConfig, CosyVoiceEngine
from protocol import Event, read_event, write_event
from speech_chunks import speech_chunks


LOGGER = logging.getLogger("jarvis_cosyvoice_worker")

_DIGIT_WORDS = {
    "0": "zero", "1": "one", "2": "two", "3": "three", "4": "four",
    "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine",
}


def normalize_spoken_decimals(text: str) -> str:
    """Make decimal points explicit for voice models that otherwise omit them."""
    def replace(match):
        fraction = " ".join(_DIGIT_WORDS[digit] for digit in match.group(2))
        return f"{match.group(1)} point {fraction}"

    return re.sub(r"(?<![\d.])(-?\d+)\.(\d+)(?![\d.])", replace, text)


def bound_spoken_text(text: str, maximum_characters: int) -> str:
    """Keep buffered Home Assistant speech responsive without altering text replies."""
    cleaned = re.sub(r"\n+Sources:\n.*", "", text, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", cleaned)
    cleaned = re.sub(r"https?://\S+", "", cleaned)
    cleaned = re.sub(r"[*_`#>|]+", "", cleaned)
    cleaned = re.sub(r"(?m)^\s*[-+]\s+", "", cleaned)
    cleaned = re.sub(r"[📌✅❌⚠️🔎📡]", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = normalize_spoken_decimals(cleaned)
    if maximum_characters <= 0 or len(cleaned) <= maximum_characters:
        return cleaned
    candidate = cleaned[: maximum_characters + 1]
    sentence_boundaries = [candidate.rfind(mark) for mark in (". ", "? ", "! ")]
    boundary = max(sentence_boundaries)
    if boundary < maximum_characters // 2:
        boundary = max(candidate.rfind(mark) for mark in ("; ", ", "))
    if boundary < maximum_characters // 2:
        boundary = candidate.rfind(" ", 0, maximum_characters + 1)
    shortened = candidate[:boundary].rstrip(" ,;:.!?")
    return shortened + "."


class Worker:
    def __init__(self, engine: CosyVoiceEngine, maximum_spoken_characters: int = 320) -> None:
        self.engine = engine
        self.maximum_spoken_characters = maximum_spoken_characters

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            while event := await read_event(reader):
                if event.type == "describe":
                    await write_event(writer, self.info())
                elif event.type == "synthesize":
                    await self.synthesize(event, writer)
        except (ConnectionError, asyncio.IncompleteReadError):
            LOGGER.debug("Client disconnected")
        except Exception:
            LOGGER.exception("CosyVoice worker request failed")
        finally:
            writer.close()
            await writer.wait_closed()

    def info(self) -> Event:
        return Event({"type": "info"}, {"tts": [{
            "name": "Project Jarvis CosyVoice Worker",
            "description": "Private streaming CosyVoice 3 Jarvis voice clone",
            "version": "0.1.0",
            "installed": self.engine.ready,
            "voices": [{
                "name": "jarvis_cosyvoice",
                "description": "Jarvis CosyVoice 3 streaming clone",
                "version": "1.0",
                "installed": self.engine.ready,
                "languages": ["en-GB"],
                "speakers": None,
            }],
            "supports_synthesize_streaming": False,
            "jarvis_status": {
                "ready": self.engine.ready,
                "last_error": self.engine.last_error,
                "model_load_seconds": round(self.engine.model_load_seconds, 3),
                "conditioning_seconds": round(self.engine.conditioning_seconds, 3),
                "last_first_audio_seconds": round(self.engine.last_first_audio_seconds, 3),
                "last_generation_seconds": round(self.engine.last_generation_seconds, 3),
            },
        }]})

    async def synthesize(self, event: Event, writer: asyncio.StreamWriter) -> None:
        text = str(event.data.get("text", "")).strip()
        if not text:
            raise ValueError("Synthesize request did not contain text")
        bounded_text = bound_spoken_text(text, 0)
        chunks = speech_chunks(bounded_text, self.maximum_spoken_characters)
        if bounded_text != text:
            LOGGER.info(
                "Bounded spoken response from %d to %d characters",
                len(text),
                len(bounded_text),
            )
        started = time.monotonic()
        audio_started = False
        sample_rate = None
        for index, chunk in enumerate(chunks):
            # Release a complete bounded text chunk, not tiny unfinished model
            # fragments. The next chunk can generate while this one plays.
            # This avoids waiting for the whole long answer before first audio.
            pcm_parts = []
            chunk_bytes = 0
            async for pcm, rate, elapsed in self.engine.synthesize_stream(chunk):
                if not pcm:
                    continue
                if rate <= 0 or len(pcm) % 2:
                    raise RuntimeError("Invalid PCM from CosyVoice")
                if sample_rate is not None and sample_rate != rate:
                    raise RuntimeError("Sample rate changed within one utterance")
                sample_rate = rate
                chunk_bytes += len(pcm)
                if chunk_bytes > 16 * 1024 * 1024:
                    raise RuntimeError("CosyVoice chunk exceeded the audio buffer limit")
                pcm_parts.append(pcm)
            if not pcm_parts:
                raise RuntimeError("CosyVoice returned no audio for a speech chunk")
            metadata = {"rate": sample_rate, "width": 2, "channels": 1}
            if not audio_started:
                await write_event(writer, Event({"type": "audio-start"}, metadata))
                audio_started = True
                LOGGER.info("First complete CosyVoice chunk ready in %.2fs", time.monotonic() - started)
            for pcm in pcm_parts:
                for offset in range(0, len(pcm), 8192):
                    await write_event(writer, Event(
                        {"type": "audio-chunk"}, metadata, pcm[offset:offset + 8192]
                    ))
            LOGGER.info("Completed speech chunk %d/%d", index + 1, len(chunks))
        if not audio_started:
            raise RuntimeError("CosyVoice returned no audio")
        await write_event(writer, Event({"type": "audio-stop"}, {}))
        LOGGER.info("CosyVoice request completed in %.2fs", time.monotonic() - started)


async def serve(config: CosyVoiceConfig, *, host: str, port: int) -> None:
    engine = CosyVoiceEngine(config)
    await engine.warmup()
    worker = Worker(
        engine,
        maximum_spoken_characters=int(
            os.getenv("COSYVOICE_MAX_SPOKEN_CHARACTERS", "320")
        ),
    )
    server = await asyncio.start_server(worker.handle, host, port)
    LOGGER.info("Jarvis CosyVoice worker listening on %s:%s", host, port)
    async with server:
        await server.serve_forever()


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    config = CosyVoiceConfig(
        model_dir=os.getenv("COSYVOICE_MODEL_DIR", CosyVoiceConfig.model_dir),
        reference_audio=os.getenv("COSYVOICE_REFERENCE_AUDIO", CosyVoiceConfig.reference_audio),
        reference_text_file=os.getenv("COSYVOICE_REFERENCE_TEXT_FILE", CosyVoiceConfig.reference_text_file),
        speaker_id=os.getenv("COSYVOICE_SPEAKER_ID", CosyVoiceConfig.speaker_id),
        speed=float(os.getenv("COSYVOICE_SPEED", "1.0")),
        fp16=os.getenv("COSYVOICE_FP16", "true").lower() in {"1", "true", "yes"},
        generation_seed=int(os.getenv("COSYVOICE_GENERATION_SEED", "20260825")),
        cue_directory=os.getenv("COSYVOICE_CUE_DIRECTORY", CosyVoiceConfig.cue_directory),
    )
    await serve(
        config,
        host=os.getenv("COSYVOICE_LISTEN_HOST", "0.0.0.0"),
        port=int(os.getenv("COSYVOICE_LISTEN_PORT", "10410")),
    )


if __name__ == "__main__":
    asyncio.run(main())
