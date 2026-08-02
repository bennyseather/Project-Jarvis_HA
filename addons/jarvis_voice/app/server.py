"""Transparent Wyoming TTS proxy with local, in-memory PCM refinement."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging

from dsp import process_pcm16
from protocol import Event, read_event, write_event


LOGGER = logging.getLogger("jarvis_voice")


@dataclass(frozen=True)
class VoiceProxyConfig:
    upstream_host: str = "core-piper"
    upstream_port: int = 10200
    profile: str = "refined"
    strength: float = 0.65
    output_gain: float = 0.92
    listen_host: str = "0.0.0.0"
    listen_port: int = 10350


class VoiceProxy:
    def __init__(self, config: VoiceProxyConfig) -> None:
        self.config = config

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
        upstream_reader, upstream_writer = await asyncio.open_connection(
            self.config.upstream_host, self.config.upstream_port
        )
        try:
            await write_event(upstream_writer, event)
            if event.type == "describe":
                response = await read_event(upstream_reader)
                if response is not None:
                    header = _disable_streaming(response.header)
                    await write_event(client, Event(header, response.data, response.payload))
                return
            if event.type != "synthesize":
                response = await read_event(upstream_reader)
                if response is not None:
                    await write_event(client, response)
                return
            await self._relay_synthesis(upstream_reader, client)
        finally:
            upstream_writer.close()
            await upstream_writer.wait_closed()

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
        metadata = start.header.get("data", {})
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
        chunk_header = {
            "type": "audio-chunk",
            "data": {"rate": rate, "width": width, "channels": channels},
        }
        for offset in range(0, len(pcm), 8192):
            await write_event(client, Event(chunk_header, payload=pcm[offset:offset + 8192]))
        await write_event(client, stop)
        LOGGER.info(
            "Processed %.2fs of Piper audio with profile=%s strength=%.2f",
            len(pcm) / max(1, rate * width * channels),
            self.config.profile,
            self.config.strength,
        )


def _disable_streaming(header: dict) -> dict:
    header = dict(header)
    data = dict(header.get("data", {}))
    for service in data.get("tts", []):
        if isinstance(service, dict):
            service["supports_synthesize_streaming"] = False
    header["data"] = data
    return header


async def run_server(config: VoiceProxyConfig) -> None:
    if config.profile not in {"refined", "synthetic", "clean"}:
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
