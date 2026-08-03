"""Transparent Wyoming TTS proxy with local, in-memory PCM refinement."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging

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


class VoiceProxy:
    def __init__(self, config: VoiceProxyConfig) -> None:
        self.config = config
        self.kokoro = KokoroEngine(KokoroConfig(voice=config.voice, speed=config.speed))

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
            await write_event(client, _kokoro_info())
            return
        if event.type == "synthesize":
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
        "version": "0.23.2",
        "attribution": attribution,
        "installed": True,
        "voices": voices,
        "supports_synthesize_streaming": False,
    }]})


def _shorten_comma_pauses(text: str) -> str:
    """Remove comma timing while retaining a word boundary."""
    return " ".join(text.replace(",", " ").split())


async def run_server(config: VoiceProxyConfig) -> None:
    if config.profile not in {"refined", "synthetic", "metallic", "clean"}:
        raise ValueError(f"Unsupported voice profile: {config.profile}")
    proxy = VoiceProxy(config)
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
