"""Transparent Wyoming TTS proxy with local, in-memory PCM refinement."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
import time

from chatterbox_engine import ChatterboxConfig, ChatterboxNanoEngine
from dsp import clarity_filter_pcm16, process_voice_pcm16, raise_pitch_and_speed_pcm16
from kokoro_engine import KokoroConfig, KokoroEngine, SUPPORTED_VOICES
from piper_m39_engine import PiperM39Config, PiperM39Engine
from protocol import Event, read_event, write_event


LOGGER = logging.getLogger("jarvis_voice")


@dataclass(frozen=True)
class VoiceProxyConfig:
    upstream_host: str = "core-piper"
    upstream_port: int = 10200
    model_package: str = "/share/jarvis_voice/jarvis-piper-m40.zip"
    model_cache_dir: str = "/data/models/m40"
    profile: str = "jarvis_v5"
    strength: float = 1.0
    output_gain: float = 0.98
    listen_host: str = "0.0.0.0"
    listen_port: int = 10350
    voice: str = "bm_george"
    speed: float = 1.08
    shorten_comma_pauses: bool = True
    pitch_factor: float = 1.055
    staccato_pause_ms: float = 25.0
    darkness: float = 0.10
    piper_fallback: bool = True
    engine: str = "qwen_1_7b"
    reference_path: str = "/app/jarvis-reference.wav"
    generation_timeout: float = 300.0
    warm_model: bool = True
    articulation_mode: str = "crisp"
    maximum_segment_characters: int = 105
    piper_noise_scale: float = 0.35
    piper_noise_w: float = 0.45
    clarity_mode: bool = True
    qwen_host: str = "127.0.0.1"
    qwen_port: int = 10400
    qwen_filter: str = "clean"
    qwen_filter_strength: float = 0.55
    qwen_connect_timeout: float = 3.0
    qwen_maximum_spoken_characters: int = 420
    qwen_buffer_before_playback: bool = True
    qwen_maximum_buffer_bytes: int = 67108864


class VoiceProxy:
    def __init__(self, config: VoiceProxyConfig) -> None:
        self.config = config
        self.kokoro = KokoroEngine(KokoroConfig(voice=config.voice, speed=config.speed))
        self.piper_m39 = PiperM39Engine(PiperM39Config(
            package_path=config.model_package,
            cache_dir=config.model_cache_dir,
            timeout=config.generation_timeout,
            noise_scale=config.piper_noise_scale,
            noise_w=config.piper_noise_w,
        ))
        self.chatterbox = ChatterboxNanoEngine(
            ChatterboxConfig(
                reference_path=config.reference_path,
                generation_timeout=config.generation_timeout,
                articulation_mode=config.articulation_mode,
                maximum_segment_characters=config.maximum_segment_characters,
            )
        )
        self.qwen_ready = False
        self.qwen_last_error = ""

    async def warmup(self) -> None:
        if self.config.engine == "qwen_1_7b":
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(self.config.qwen_host, self.config.qwen_port),
                    self.config.qwen_connect_timeout,
                )
                await write_event(writer, Event({"type": "describe"}, {}))
                response = await asyncio.wait_for(
                    read_event(reader), self.config.qwen_connect_timeout
                )
                writer.close()
                await writer.wait_closed()
                if response is None or response.type != "info":
                    raise RuntimeError("Qwen worker returned no service information")
                self.qwen_ready = True
                self.qwen_last_error = ""
                LOGGER.info("Qwen worker is ready at %s:%s", self.config.qwen_host, self.config.qwen_port)
            except Exception as error:
                self.qwen_ready = False
                self.qwen_last_error = str(error)[:300]
                LOGGER.exception("Qwen worker is unavailable; local fallbacks remain available")
            return
        if self.config.engine in {"piper_m39", "piper_m40"}:
            try:
                await self.piper_m39.prepare()
                LOGGER.info("%s Piper voice is ready", self.config.engine.upper())
            except Exception as error:
                self.piper_m39.last_error = str(error)
                LOGGER.exception("Private Piper preparation failed; neural fallbacks remain available")
            return
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
                ready=self.qwen_ready if self.config.engine == "qwen_1_7b" else self.piper_m39.ready if self.config.engine in {"piper_m39", "piper_m40"} else self.chatterbox.ready,
                last_error=self.qwen_last_error if self.config.engine == "qwen_1_7b" else self.piper_m39.last_error if self.config.engine in {"piper_m39", "piper_m40"} else self.chatterbox.last_error,
                last_generation_seconds=self.piper_m39.last_generation_seconds if self.config.engine in {"piper_m39", "piper_m40"} else self.chatterbox.last_generation_seconds,
                conditioning_seconds=self.chatterbox.conditioning_seconds,
                warmup_seconds=self.chatterbox.warmup_seconds,
                last_first_audio_seconds=self.chatterbox.last_first_audio_seconds,
            ))
            return
        if event.type == "synthesize":
            requested_voice = _requested_voice(event)
            if (
                self.config.engine == "qwen_1_7b"
                and requested_voice in {None, "jarvis_qwen", "jarvis_neural"}
            ):
                try:
                    await self._synthesize_qwen(event, client)
                    return
                except Exception:
                    LOGGER.exception("Qwen synthesis failed; trying local fallback")
            if (
                self.config.engine in {"piper_m39", "piper_m40"}
                and requested_voice in {None, "jarvis_m39", "jarvis_m40", "jarvis_neural"}
            ):
                try:
                    await self._synthesize_piper_m39(event, client)
                    return
                except Exception:
                    LOGGER.exception("Private Piper synthesis failed; trying neural fallback")
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

    async def _synthesize_qwen(self, event: Event, client: asyncio.StreamWriter) -> None:
        text = _bounded_spoken_text(
            str(event.data.get("text", "")), self.config.qwen_maximum_spoken_characters
        )
        if not text:
            raise ValueError("Synthesize request did not contain text")
        event = Event(dict(event.header), {**event.data, "text": text}, event.payload)
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(self.config.qwen_host, self.config.qwen_port),
            self.config.qwen_connect_timeout,
        )
        started = time.monotonic()
        try:
            await write_event(writer, event)
            if self.config.qwen_filter == "clean":
                relay = (
                    self._relay_synthesis_buffered(reader, client)
                    if self.config.qwen_buffer_before_playback
                    else self._relay_synthesis_streaming(reader, client)
                )
            else:
                relay = self._relay_synthesis(
                    reader,
                    client,
                    profile_name=self.config.qwen_filter,
                    strength=self.config.qwen_filter_strength,
                )
            # The timeout is deliberately large on CPU. It prevents an abandoned
            # request from running forever without replacing Qwen merely for being slow.
            await asyncio.wait_for(relay, self.config.generation_timeout)
        finally:
            writer.close()
            await writer.wait_closed()
        LOGGER.info(
            "Qwen response relayed in %.2fs with filter=%s delivery=%s",
            time.monotonic() - started,
            self.config.qwen_filter,
            "buffered" if self.config.qwen_buffer_before_playback else "streaming",
        )

    async def _relay_synthesis_buffered(
        self, upstream: asyncio.StreamReader, client: asyncio.StreamWriter
    ) -> None:
        """Expose Qwen audio only after the complete stream is locally buffered."""
        start: Event | None = None
        stop: Event | None = None
        chunks: list[bytes] = []
        total = 0
        while response := await read_event(upstream):
            if response.type == "audio-start":
                start = response
            elif response.type == "audio-chunk":
                total += len(response.payload)
                if total > self.config.qwen_maximum_buffer_bytes:
                    raise RuntimeError("Qwen audio exceeded the configured buffer limit")
                chunks.append(response.payload)
            elif response.type == "audio-stop":
                stop = response
                break
        if start is None or stop is None or not chunks:
            raise RuntimeError("Qwen worker returned an incomplete buffered audio stream")
        await write_event(client, start)
        metadata = dict(start.data)
        for pcm in chunks:
            await write_event(client, Event({"type": "audio-chunk"}, metadata, pcm))
        await write_event(client, stop)
        LOGGER.info("Buffered %.2f MiB of Qwen audio before playback exposure", total / 1048576)

    async def _relay_synthesis_streaming(
        self, upstream: asyncio.StreamReader, client: asyncio.StreamWriter
    ) -> None:
        """Forward clean Qwen PCM as it arrives, preserving time-to-first-audio."""
        started = False
        stopped = False
        try:
            while response := await read_event(upstream):
                if response.type == "audio-start":
                    started = True
                elif response.type == "audio-stop":
                    stopped = True
                await write_event(client, response)
                if stopped:
                    break
        except Exception:
            if not started:
                raise
            LOGGER.exception(
                "Qwen stream failed after audio began; closing partial Qwen audio without fallback"
            )
            await write_event(client, Event({"type": "audio-stop"}, {}))
            return
        if not started or not stopped:
            if started:
                LOGGER.warning(
                    "Qwen stream ended after partial audio; closing it without changing voice"
                )
                await write_event(client, Event({"type": "audio-stop"}, {}))
                return
            raise RuntimeError("Qwen worker returned an incomplete audio stream")

    async def _synthesize_piper_m39(self, event: Event, client: asyncio.StreamWriter) -> None:
        text = str(event.data.get("text", "")).strip()
        if not text:
            raise ValueError("Synthesize request did not contain text")
        if self.config.shorten_comma_pauses:
            text = _shorten_comma_pauses(text)
        started = time.monotonic()
        pcm, rate = await self.piper_m39.synthesize(text)
        if self.config.clarity_mode:
            pcm = clarity_filter_pcm16(pcm, rate)
        else:
            pcm = raise_pitch_and_speed_pcm16(pcm, self.config.pitch_factor)
            pcm = process_voice_pcm16(
                pcm, rate, 1, self.config.profile,
                self.config.strength, self.config.output_gain,
                self.config.staccato_pause_ms, self.config.darkness,
            )
        metadata = {"rate": rate, "width": 2, "channels": 1}
        await write_event(client, Event({"type": "audio-start"}, metadata))
        for offset in range(0, len(pcm), 8192):
            await write_event(client, Event(
                {"type": "audio-chunk"}, metadata, pcm[offset:offset + 8192]
            ))
        await write_event(client, Event({"type": "audio-stop"}, {}))
        LOGGER.info(
            "%s Piper response ready in %.2fs; audio=%.2fs",
            self.config.engine.upper(),
            time.monotonic() - started, len(pcm) / max(1, rate * 2),
        )

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
        pcm = process_voice_pcm16(
            pcm, rate, 1, self.config.profile,
            self.config.strength, self.config.output_gain,
            self.config.staccato_pause_ms,
            self.config.darkness,
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
        started = time.monotonic()
        audio_started = False
        total_bytes = 0
        rate = 24000
        try:
            async for pcm, rate, segment, generation_seconds in self.chatterbox.synthesize_segments(text):
                pcm = raise_pitch_and_speed_pcm16(pcm, self.config.pitch_factor)
                pcm = process_voice_pcm16(
                    pcm, rate, 1, self.config.profile,
                    self.config.strength, self.config.output_gain,
                    self.config.staccato_pause_ms,
                    self.config.darkness,
                )
                metadata = {"rate": rate, "width": 2, "channels": 1}
                if not audio_started:
                    await write_event(client, Event({"type": "audio-start"}, metadata))
                    audio_started = True
                    first_audio_seconds = time.monotonic() - started
                    self.chatterbox.last_first_audio_seconds = first_audio_seconds
                    LOGGER.info("First Chatterbox audio ready in %.2fs", first_audio_seconds)
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
        self,
        upstream: asyncio.StreamReader,
        client: asyncio.StreamWriter,
        *,
        profile_name: str | None = None,
        strength: float | None = None,
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
            pcm = process_voice_pcm16(
                pcm, rate, channels, profile_name or self.config.profile,
                self.config.strength if strength is None else strength,
                self.config.output_gain,
                self.config.staccato_pause_ms,
                self.config.darkness,
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
            profile_name or self.config.profile,
            self.config.strength if strength is None else strength,
        )


def _refine_info(event: Event) -> Event:
    data = dict(event.data)
    for service in data.get("tts", []):
        if isinstance(service, dict):
            service["supports_synthesize_streaming"] = False
            service["name"] = "Project Jarvis Voice"
            service["description"] = "Locally refined British synthetic Piper voice"
    return Event(dict(event.header), data, event.payload)


def _bounded_spoken_text(text: str, maximum: int) -> str:
    """Bound unusually long TTS payloads at a natural sentence boundary."""
    normalized = " ".join(str(text).split())
    maximum = max(120, min(1000, int(maximum)))
    if len(normalized) <= maximum:
        return normalized
    candidate = normalized[: maximum + 1]
    boundary = max(candidate.rfind(". "), candidate.rfind("? "), candidate.rfind("! "))
    if boundary >= maximum // 2:
        return candidate[: boundary + 1]
    boundary = candidate.rfind(" ", 0, maximum + 1)
    return candidate[:boundary].rstrip(" ,;:") + "."


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
        "version": "0.34.3",
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
    conditioning_seconds: float = 0.0,
    warmup_seconds: float = 0.0,
    last_first_audio_seconds: float = 0.0,
) -> Event:
    event = _kokoro_info()
    service = event.data["tts"][0]
    service["name"] = "Project Jarvis High Quality Voice"
    service["description"] = (
            "Qwen3-TTS 1.7B cloned Jarvis voice with selectable local finishing filters"
        if engine == "qwen_1_7b"
        else
            "Private M40 Jarvis Piper voice with local neural fallbacks"
        if engine == "piper_m40"
        else "Private M39 Jarvis Piper voice with local neural fallbacks"
        if engine == "piper_m39"
        else "Streaming Chatterbox Nano CPU voice with Kokoro and Piper fallbacks"
        if engine == "chatterbox_nano" else "Local Kokoro British voice with Piper fallback"
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
        "conditioning_seconds": round(conditioning_seconds, 3),
        "warmup_seconds": round(warmup_seconds, 3),
        "last_first_audio_seconds": round(last_first_audio_seconds, 3),
    }
    service["voices"].insert(0, {
        "name": "jarvis_neural",
        "description": "Jarvis Neural (approved crisp synthetic reference)",
        "version": "1.0",
        "attribution": {
            "name": "Chatterbox Nano by Resemble AI",
            "url": "https://github.com/resemble-ai/chatterbox",
        },
        "installed": engine == "chatterbox_nano",
        "languages": ["en-GB"],
        "speakers": None,
    })
    if engine == "qwen_1_7b":
        service["voices"].insert(0, {
            "name": "jarvis_qwen",
            "description": "Jarvis Qwen 1.7B (private approved reference)",
            "version": "1.0",
            "attribution": {
                "name": "Qwen3-TTS by Qwen",
                "url": "https://github.com/QwenLM/Qwen3-TTS",
            },
            "installed": True,
            "languages": ["en-GB"],
            "speakers": None,
        })
    if engine in {"piper_m39", "piper_m40"}:
        service["voices"].insert(0, {
            "name": "jarvis_m40" if engine == "piper_m40" else "jarvis_m39",
            "description": "Jarvis M40 (private dedicated Piper model)" if engine == "piper_m40" else "Jarvis M39 (private dedicated Piper model)",
            "version": "1.0",
            "attribution": {"name": "Private Project Jarvis model", "url": ""},
            "installed": ready,
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
    if config.engine not in {"qwen_1_7b", "piper_m39", "piper_m40", "chatterbox_nano", "kokoro"}:
        raise ValueError(f"Unsupported voice engine: {config.engine}")
    if config.profile not in {
        "jarvis_v5", "refined", "synthesized", "synthetic", "metallic", "clean"
    }:
        raise ValueError(f"Unsupported voice profile: {config.profile}")
    if config.articulation_mode not in {"crisp", "balanced"}:
        raise ValueError(f"Unsupported articulation mode: {config.articulation_mode}")
    if config.qwen_filter not in {"clean", "refined", "synthesized", "synthetic", "metallic"}:
        raise ValueError(f"Unsupported Qwen filter: {config.qwen_filter}")
    if not 1048576 <= config.qwen_maximum_buffer_bytes <= 268435456:
        raise ValueError("qwen_maximum_buffer_bytes must be between 1 MiB and 256 MiB")
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
