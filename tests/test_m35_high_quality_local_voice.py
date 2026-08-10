import asyncio
import struct
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / "home_assistant/addons/jarvis_voice"
sys.path.insert(0, str(ADDON / "app"))

from chatterbox_engine import split_spoken_segments  # noqa: E402
from protocol import Event, read_event  # noqa: E402
from server import VoiceProxy, VoiceProxyConfig, _requested_voice, _voice_info  # noqa: E402


class MemoryWriter:
    def __init__(self):
        self.buffer = bytearray()

    def write(self, data):
        self.buffer.extend(data)

    async def drain(self):
        return None


class FakeChatterbox:
    ready = True
    last_error = ""
    last_generation_seconds = 0.02
    last_first_audio_seconds = 0.0

    async def synthesize_segments(self, text):
        for segment in split_spoken_segments(text, 35):
            yield struct.pack("<400h", *([1000] * 400)), 24000, segment, 0.02


class M35HighQualityLocalVoiceTests(unittest.IsolatedAsyncioTestCase):
    def test_sentence_segmentation_is_bounded_and_lossless(self):
        text = "Systems are ready. The office is secure and operating normally."
        segments = split_spoken_segments(text, 35)
        self.assertGreaterEqual(len(segments), 2)
        self.assertEqual(" ".join(segments), text)
        self.assertTrue(all(len(segment) <= 35 for segment in segments))

    async def test_chatterbox_sends_audio_before_all_segments_finish(self):
        proxy = VoiceProxy(VoiceProxyConfig(engine="chatterbox_nano"))
        proxy.chatterbox = FakeChatterbox()
        writer = MemoryWriter()
        await proxy._synthesize_chatterbox(
            Event({"type": "synthesize"}, {"text": "First reply. Second reply."}),
            writer,
        )
        reader = asyncio.StreamReader()
        reader.feed_data(bytes(writer.buffer))
        reader.feed_eof()
        self.assertEqual((await read_event(reader)).type, "audio-start")
        chunk_count = 0
        while event := await read_event(reader):
            if event.type == "audio-chunk":
                chunk_count += 1
            if event.type == "audio-stop":
                break
        self.assertGreaterEqual(chunk_count, 2)

    def test_service_advertises_streaming_neural_and_fallback_voices(self):
        service = _voice_info("chatterbox_nano").data["tts"][0]
        self.assertFalse(service["supports_synthesize_streaming"])
        self.assertEqual(service["voices"][0]["name"], "jarvis_neural")
        self.assertIn("bm_daniel", {voice["name"] for voice in service["voices"]})
        self.assertIn("jarvis_status", service)

    def test_voice_selection_supports_neural_and_kokoro_ab_testing(self):
        neural = Event({"type": "synthesize"}, {
            "text": "Test", "voice": {"name": "jarvis_neural"}
        })
        daniel = Event({"type": "synthesize"}, {
            "text": "Test", "voice": {"name": "bm_daniel"}
        })
        self.assertEqual(_requested_voice(neural), "jarvis_neural")
        self.assertEqual(_requested_voice(daniel), "bm_daniel")

    def test_addon_is_cpu_bounded_migration_ready_and_has_fallbacks(self):
        dockerfile = (ADDON / "Dockerfile").read_text(encoding="utf-8")
        config = (ADDON / "config.yaml").read_text(encoding="utf-8")
        server = (ADDON / "app/server.py").read_text(encoding="utf-8")
        docs = (ADDON / "DOCS.md").read_text(encoding="utf-8")
        self.assertIn(
            "chatterbox.git@5de7a54aa4e5e2baadb0182dde554908b48b85c2",
            dockerfile,
        )
        self.assertIn("FROM python:3.13-slim", dockerfile)
        self.assertIn("kokoro-onnx==0.5.0", dockerfile)
        self.assertIn('engine: list(piper_m40|piper_m39|chatterbox_nano|kokoro)', config)
        self.assertIn("generation_timeout", config)
        self.assertIn("OMP_NUM_THREADS=4", dockerfile)
        self.assertIn("trying Kokoro", server)
        self.assertIn("Piper", docs)
        self.assertIn("separate", docs.casefold())


if __name__ == "__main__":
    unittest.main()
