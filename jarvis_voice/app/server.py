"""Transparent Wyoming TTS proxy with local, in-memory PCM refinement."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
import time

from chatterbox_engine import ChatterboxConfig, ChatterboxNanoEngine
from dsp import process_pcm16, raise_pitch_and_speed_pcm16
from kokoro_engine import KokoroConfig, KokoroEngine, SUPPORTED_VOICES
from protocol import Event, read_event, write_event


LOGGER = logging.getLogger("jarvis_voice")


@dataclass(frozen=True)
class VoiceProxyConfig:
    upstream_host: str = "core-piper"
    upstream_port: int = 10200
    profile: str = "metallic"
    strength: float = 0.92
    output_gain: float = 0.92
    listen_host: str = "0.0.0.0"
    listen_port: int = 10350
    voice: str = "bm_george"
    speed: float = 1.08
    shorten_comma_pauses: bool = True
    pitch_factor: float = 1.10
    piper_fallback: bool = True
    engine: str = "chatterbox_nano"
    reference_path: str = "/app/jarvis-reference.wav"
    generation_timeout: float = 30.0
    warm_model: bool = True


class VoiceProxy:
    def __init__(self, config: VoiceProxyConfig) -> None:
        self.config = config
        self.kokoro = KokoroEngine(KokoroConfig(voice=config.voice, speed=config.speed))
        self.chatterbox = ChatterboxNanoEngine(
            ChatterboxConfig(
                reference_path=config.reference_path,
                generation_timeout=config.generation_timeout,
            )
        )

    async def warmup(self) -> None:
        if self.config.engine != "chatterbox_nano" or not self.config.warm_model:
            return
        try:
            await asyncio.wait_for(
                self.chatterbox.warmup(), self.config.generation_timeout
            )
            LOGGER.info("Chatterbox Nano is ready")
        except Exception:
            LOGGER.exception("Chatterbox warmup failed; Kokoro remains available")

    async def handle(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            while event := await read_event(reader):
                await self._handle_event(event, writer)
        except (ConnectionError, asyncio.IncompleteReadError):
            LOGGER.debug("Wyoming client disconnected")
        except Exception:
            LOGGER.exception("Voice request failed")
        finally:
            writer.close()
            await writer.wait_closed()

    async def _handle_event(self, event: Event, client: asyncio.StreamWriter) -> None:
        if event.type == "describe":
            await write_event(client, _voice_info(
                self.config.engine,
                ready=self.chatterbox.ready,
                last_error=self.chatterbox.last_error,
                last_generation_seconds=self.chatterbox.last_generation_seconds,
            ))
            return
        if event.type == "synthesize":
            requested_voice = _requested_voice(event)
            if (
                self.config.engine == "chatterbox_nano"
                and requested_voice in {None, "jarvis_neural"}
            ):
                try:
                    await self._synthesize_chatterbox(event, client)
                    return
                except Exception:
                    LOGGER.exception("Chatterbox synthesis failed; trying Kokoro")
            try:
                await self._synthesize_kokoro(event, client)
                return
            except Exception:
                LOGGER.exception("Local Kokoro synthesis failed")
                if not self.config.piper_fallback:
                    raise
        upstream_reader, upstream_writer = await asyncio.open_connection(
            self.config.upstream_host, self.config.upstream_port
        )
        try:
            await write_event(upstream_writer, event)
            if event.type != "synthesize":
                response = await read_event(upstream_reader)
                if response is not None:
                    await write_event(client, response)
                return
            await self._relay_synthesis(upstream_reader, client)
        finally:
            upstream_writer.close()
            await upstream_writer.wait_closed()

    async def _synthesize_kokoro(self, event: Event, client: asyncio.StreamWriter) -> None:
        text = str(event.data.get("text", "")).strip()
        if not text:
            raise ValueError("Synthesize request did not contain text")
        if self.config.shorten_comma_pauses:
            text = _shorten_comma_pauses(text)
        requested_voice = event.data.get("voice") or {}
        voice = requested_voice.get("name") if isinstance(requested_voice, dict) else None
        pcm, rate = await self.kokoro.synthesize(text, voice)
        pcm = raise_pitch_and_speed_pcm16(pcm, self.config.pitch_factor)
        pcm = process_pcm16(
            pcm, rate, 1, self.config.profile,
            self.config.strength, self.config.output_gain,
        )
        audio_data = {"rate": rate, "width": 2, "channels": 1}
        await write_event(client, Event({"type": "audio-start"}, audio_data))
        for offset in range(0, len(pcm), 8192):
            await write_event(client, Event(
                {"type": "audio-chunk"}, audio_data, pcm[offset:offset + 8192]
            ))
        await write_event(client, Event({"type": "audio-stop"}, {}))
        LOGGER.info("Synthesized %.2fs with Kokoro voice=%s", len(pcm) / (rate * 2), voice or self.config.voice)

    async def _synthesize_chatterbox(self, event: Event, client: asyncio.StreamWriter) -> None:
        text = str(event.data.get("text", "")).strip()
        if not text:
            raise ValueError("Synthesize request did not contain text")
        if self.config.shorten_comma_pauses:
            text = _shorten_comma_pauses(text)
        started = time.monotonic()
        audio_started = False
        total_bytes = 0
        rate = 24000
        try:
            async for pcm, rate, segment, generation_seconds in self.chatterbox.synthesize_segments(text):
                pcm = raise_pitch_and_speed_pcm16(pcm, self.config.pitch_factor)
                pcm = process_pcm16(
                    pcm, rate, 1, self.config.profile,
                    self.config.strength, self.config.output_gain,
                )
                metadata = {"rate": rate, "width": 2, "channels": 1}
                if not audio_started:
                    await write_event(client, Event({"type": "audio-start"}, metadata))
                    audio_started = True
                    LOGGER.info("First Chatterbox audio ready in %.2fs", time.monotonic() - started)
                for offset in range(0, len(pcm), 8192):
                    await write_event(client, Event(
                        {"type": "audio-chunk"}, metadata, pcm[offset:offset + 8192]
                    ))
                total_bytes += len(pcm)
                LOGGER.info("Generated segment in %.2fs: %s", generation_seconds, segment[:80])
        except Exception:
            if not audio_started:
                raise
            LOGGER.exception("Later Chatterbox segment failed; closing the valid partial stream")
        if not audio_started:
            raise RuntimeError("Chatterbox returned no audio")
        await write_event(client, Event({"type": "audio-stop"}, {}))
        LOGGER.info(
            "Chatterbox request complete in %.2fs; audio=%.2fs",
            time.monotonic() - started, total_bytes / max(1, rate * 2),
        )

    async def _relay_synthesis(
        self, upstream: asyncio.StreamReader, client: asyncio.StreamWriter
    ) -> None:
        start: Event | None = None
        stop: Event | None = None
        chunks: list[bytes] = []
        while response := await read_event(upstream):
            if response.type == "audio-start":
                start = response
            elif response.type == "audio-chunk":
                chunks.append(response.payload)
            elif response.type == "audio-stop":
                stop = response
                break
            else:
                await write_event(client, response)
        if start is None or stop is None:
            raise RuntimeError("Piper returned an incomplete audio stream")
        metadata = start.data
        rate = int(metadata.get("rate", 22050))
        width = int(metadata.get("width", 2))
        channels = int(metadata.get("channels", 1))
        pcm = b"".join(chunks)
        if width == 2:
            pcm = process_pcm16(
                pcm, rate, channels, self.config.profile,
                self.config.strength, self.config.output_gain,
            )
        await write_event(client, start)
        chunk_data = {"rate": rate, "width": width, "channels": channels}
        for offset in range(0, len(pcm), 8192):
            await write_event(client, Event(
                {"type": "audio-chunk"}, chunk_data, pcm[offset:offset + 8192]
            ))
        await write_event(client, stop)
        LOGGER.info(
            "Processed %.2fs of Piper audio with profile=%s strength=%.2f",
            len(pcm) / max(1, rate * width * channels),
            self.config.profile,
            self.config.strength,
        )


def _refine_info(event: Event) -> Event:
    data = dict(event.data)
    for service in data.get("tts", []):
        if isinstance(service, dict):
            service["supports_synthesize_streaming"] = False
            service["name"] = "Project Jarvis Voice"
            service["description"] = "Locally refined British synthetic Piper voice"
    return Event(dict(event.header), data, event.payload)


def _kokoro_info() -> Event:
    attribution = {"name": "Kokoro-82M", "url": "https://huggingface.co/hexgrad/Kokoro-82M"}
    voices = [{
        "name": voice,
        "description": voice.replace("bm_", "").title(),
        "version": "1.0",
        "attribution": attribution,
        "installed": True,
        "languages": ["en-GB"],
        "speakers": None,
    } for voice in SUPPORTED_VOICES]
    return Event({"type": "info"}, {"tts": [{
        "name": "Project Jarvis Neural Voice",
        "description": "Local British neural voice with restrained synthetic character",
        "version": "0.26.3",
        "attribution": attribution,
        "installed": True,
        "voices": voices,
        "supports_synthesize_streaming": False,
    }]})


def _voice_info(
    engine: str,
    *,
    ready: bool = False,
    last_error: str = "",
    last_generation_seconds: float = 0.0,
) -> Event:
    event = _kokoro_info()
    service = event.data["tts"][0]
    service["name"] = "Project Jarvis High Quality Voice"
    service["description"] = (
        "Streaming Chatterbox Nano CPU voice with Kokoro and Piper fallbacks"
        if engine == "chatterbox_nano"
        else "Local Kokoro British voice with Piper fallback"
    )
    # Wyoming's streaming capability describes incremental *text input*
    # (synthesize-start/chunk/stop), not audio chunks in the response. Jarvis
    # accepts complete synthesize events and always streams PCM output.
    service["supports_synthesize_streaming"] = False
    service["jarvis_status"] = {
        "engine": engine,
        "ready": ready,
        "last_error": last_error[:300],
        "last_generation_seconds": round(last_generation_seconds, 3),
    }
    service["voices"].insert(0, {
        "name": "jarvis_neural",
        "description": "Jarvis Neural (original British synthetic reference)",
        "version": "1.0",
        "attribution": {
            "name": "Chatterbox Nano by Resemble AI",
            "url": "https://github.com/resemble-ai/chatterbox",
        },
        "installed": engine == "chatterbox_nano",
        "languages": ["en-GB"],
        "speakers": None,
    })
    return event


def _requested_voice(event: Event) -> str | None:
    requested = event.data.get("voice") or {}
    if isinstance(requested, dict) and isinstance(requested.get("name"), str):
        return requested["name"]
    return None


def _shorten_comma_pauses(text: str) -> str:
    """Remove comma timing while retaining a word boundary."""
    return " ".join(text.replace(",", " ").split())


async def run_server(config: VoiceProxyConfig) -> None:
    if config.profile not in {"refined", "synthetic", "metallic", "clean"}:
        raise ValueError(f"Unsupported voice profile: {config.profile}")
    proxy = VoiceProxy(config)
    await proxy.warmup()
    server = await asyncio.start_server(
        proxy.handle, config.listen_host, config.listen_port
    )
    LOGGER.info(
        "Jarvis Voice listening on %s:%s; Piper=%s:%s; profile=%s",
        config.listen_host, config.listen_port,
        config.upstream_host, config.upstream_port, config.profile,
    )
    async with server:
        await server.serve_forever()
