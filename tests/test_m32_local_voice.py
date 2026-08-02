import asyncio
import struct
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / "home_assistant" / "addons" / "jarvis_voice"
sys.path.insert(0, str(ADDON / "app"))

from dsp import PROFILES, process_pcm16  # noqa: E402
from protocol import Event, read_event, write_event  # noqa: E402
from server import VoiceProxy, VoiceProxyConfig, _disable_streaming  # noqa: E402


class MemoryWriter:
    def __init__(self):
        self.buffer = bytearray()

    def write(self, data):
        self.buffer.extend(data)

    async def drain(self):
        return None


class M32LocalVoiceTests(unittest.IsolatedAsyncioTestCase):
    def test_profiles_are_bounded_distinct_and_preserve_pcm_shape(self):
        samples = [round(14000 * ((index % 31) / 15 - 1)) for index in range(1600)]
        pcm = struct.pack(f"<{len(samples)}h", *samples)
        outputs = {
            name: process_pcm16(pcm, 16000, 1, name, 0.7, 0.92)
            for name in PROFILES
        }
        self.assertTrue(all(len(value) == len(pcm) for value in outputs.values()))
        self.assertEqual(len(set(outputs.values())), 3)
        for output in outputs.values():
            decoded = struct.unpack(f"<{len(samples)}h", output)
            self.assertLessEqual(max(decoded), 32767)
            self.assertGreaterEqual(min(decoded), -32768)

    def test_bypass_conditions_and_zero_strength(self):
        pcm = struct.pack("<4h", -1000, 0, 1000, 2000)
        self.assertEqual(process_pcm16(pcm, 16000, 2, "refined", 1, 1), pcm)
        zero = process_pcm16(pcm, 16000, 1, "refined", 0, 1)
        self.assertEqual(len(zero), len(pcm))

    async def test_wyoming_framing_round_trip(self):
        writer = MemoryWriter()
        original = Event(
            {"type": "audio-chunk", "data": {"rate": 16000}},
            data=b'{"channels":1}', payload=b"\x01\x02\x03\x04",
        )
        await write_event(writer, original)
        reader = asyncio.StreamReader()
        reader.feed_data(bytes(writer.buffer))
        reader.feed_eof()
        self.assertEqual(await read_event(reader), original)

    async def test_proxy_refines_complete_upstream_audio_stream(self):
        pcm = struct.pack("<8h", -8000, -4000, -1000, 0, 1000, 4000, 8000, 2000)

        async def upstream(reader, writer):
            request = await read_event(reader)
            self.assertEqual(request.type, "synthesize")
            await write_event(writer, Event({"type": "audio-start", "data": {
                "rate": 16000, "width": 2, "channels": 1,
            }}))
            await write_event(writer, Event({"type": "audio-chunk", "data": {
                "rate": 16000, "width": 2, "channels": 1,
            }}, payload=pcm))
            await write_event(writer, Event({"type": "audio-stop"}))
            writer.close()
            await writer.wait_closed()

        server = await asyncio.start_server(upstream, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        client = MemoryWriter()
        proxy = VoiceProxy(VoiceProxyConfig(
            upstream_host="127.0.0.1", upstream_port=port,
            profile="synthetic", strength=1.0, output_gain=0.9,
        ))
        try:
            await proxy._handle_event(
                Event({"type": "synthesize", "data": {"text": "Test"}}), client
            )
        finally:
            server.close()
            await server.wait_closed()
        reader = asyncio.StreamReader()
        reader.feed_data(bytes(client.buffer))
        reader.feed_eof()
        self.assertEqual((await read_event(reader)).type, "audio-start")
        chunk = await read_event(reader)
        self.assertEqual(chunk.type, "audio-chunk")
        self.assertEqual(len(chunk.payload), len(pcm))
        self.assertNotEqual(chunk.payload, pcm)
        self.assertEqual((await read_event(reader)).type, "audio-stop")

    def test_proxy_disables_streaming_advertisement(self):
        header = {"type": "info", "data": {"tts": [
            {"supports_synthesize_streaming": True, "models": []}
        ]}}
        result = _disable_streaming(header)
        self.assertFalse(result["data"]["tts"][0]["supports_synthesize_streaming"])

    def test_addon_is_local_configurable_and_documents_fallback(self):
        config = (ADDON / "config.yaml").read_text(encoding="utf-8")
        docs = (ADDON / "DOCS.md").read_text(encoding="utf-8")
        server = (ADDON / "app" / "server.py").read_text(encoding="utf-8")
        self.assertIn('version: "0.22.0"', config)
        self.assertIn('profile: list(refined|synthetic|clean)', config)
        self.assertIn("core-piper", config)
        self.assertIn("Normal Piper remains", docs)
        self.assertIn("never written to disk", docs)
        self.assertNotIn("openai", server.casefold())
        self.assertNotIn("elevenlabs", server.casefold())


if __name__ == "__main__":
    unittest.main()
