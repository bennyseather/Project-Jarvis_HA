"""Standalone private Qwen3-TTS Wyoming worker."""

from __future__ import annotations

import asyncio
import logging
import os
import time

from protocol import Event, read_event, write_event
from qwen_engine import QwenConfig, QwenVoiceEngine


LOGGER = logging.getLogger("jarvis_qwen_worker")


class Worker:
    def __init__(self, engine: QwenVoiceEngine) -> None:
        self.engine = engine

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
            LOGGER.exception("Qwen worker request failed")
        finally:
            writer.close()
            await writer.wait_closed()

    def info(self) -> Event:
        return Event({"type": "info"}, {"tts": [{
            "name": "Project Jarvis Qwen Worker",
            "description": "Private warm Qwen3-TTS 1.7B voice-clone worker",
            "version": "0.33.0",
            "installed": self.engine.ready,
            "voices": [{
                "name": "jarvis_qwen", "description": "Jarvis Qwen 1.7B",
                "version": "1.0", "installed": self.engine.ready,
                "languages": ["en-GB"], "speakers": None,
            }],
            "supports_synthesize_streaming": False,
            "jarvis_status": {
                "ready": self.engine.ready,
                "last_error": self.engine.last_error,
                "model_load_seconds": round(self.engine.model_load_seconds, 3),
                "prompt_encode_seconds": round(self.engine.prompt_encode_seconds, 3),
                "last_generation_seconds": round(self.engine.last_generation_seconds, 3),
                "last_first_audio_seconds": round(self.engine.last_first_audio_seconds, 3),
                "response_cache_entries": len(self.engine._response_cache),
                "cache_hits": self.engine.cache_hits,
                "cache_misses": self.engine.cache_misses,
            },
        }]})

    async def synthesize(self, event: Event, writer: asyncio.StreamWriter) -> None:
        text = str(event.data.get("text", "")).strip()
        if not text:
            raise ValueError("Synthesize request did not contain text")
        started = time.monotonic()
        audio_started = False
        async for pcm, rate, segment, seconds in self.engine.synthesize_segments(text):
            metadata = {"rate": rate, "width": 2, "channels": 1}
            if not audio_started:
                await write_event(writer, Event({"type": "audio-start"}, metadata))
                audio_started = True
            for offset in range(0, len(pcm), 8192):
                await write_event(writer, Event(
                    {"type": "audio-chunk"}, metadata, pcm[offset:offset + 8192]
                ))
            LOGGER.info(
                "%s segment in %.2fs: %s",
                "Cached" if seconds == 0.0 else "Generated", seconds, segment[:100]
            )
        if not audio_started:
            raise RuntimeError("Qwen returned no audio")
        await write_event(writer, Event({"type": "audio-stop"}, {}))
        LOGGER.info("Request completed in %.2fs", time.monotonic() - started)


async def serve(config: QwenConfig, *, host: str, port: int) -> None:
    engine = QwenVoiceEngine(config)
    await engine.warmup()
    worker = Worker(engine)
    server = await asyncio.start_server(worker.handle, host, port)
    LOGGER.info("Jarvis Qwen worker listening on %s:%s", host, port)
    async with server:
        await server.serve_forever()


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    config = QwenConfig(
        model=os.getenv("QWEN_MODEL", QwenConfig.model),
        reference_audio=os.getenv("QWEN_REFERENCE_AUDIO", QwenConfig.reference_audio),
        reference_text_file=os.getenv("QWEN_REFERENCE_TEXT_FILE", QwenConfig.reference_text_file),
        cache_dir=os.getenv("QWEN_CACHE_DIR", QwenConfig.cache_dir),
        device=os.getenv("QWEN_DEVICE", QwenConfig.device),
        dtype=os.getenv("QWEN_DTYPE", QwenConfig.dtype),
        cpu_threads=int(os.getenv("QWEN_CPU_THREADS", "6")),
        maximum_segment_characters=int(os.getenv("QWEN_MAXIMUM_SEGMENT_CHARACTERS", "180")),
        response_cache_entries=int(os.getenv("QWEN_RESPONSE_CACHE_ENTRIES", "24")),
    )
    host = os.getenv("QWEN_LISTEN_HOST", "0.0.0.0")
    port = int(os.getenv("QWEN_LISTEN_PORT", "10400"))
    await serve(config, host=host, port=port)


if __name__ == "__main__":
    asyncio.run(main())
