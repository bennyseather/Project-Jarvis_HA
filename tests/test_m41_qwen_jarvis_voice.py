import asyncio
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / "home_assistant" / "addons" / "jarvis_voice"
WORKER = ROOT / "deployment" / "qwen_voice_worker"
sys.path.insert(0, str(ADDON / "app"))
sys.path.insert(0, str(ADDON))
sys.path.append(str(WORKER))

from addon_entrypoint import load_config  # noqa: E402
from dsp import PROFILES, process_voice_pcm16  # noqa: E402
from qwen_engine import QwenConfig, QwenVoiceEngine, split_segments  # noqa: E402
from server import VoiceProxyConfig, _voice_info  # noqa: E402


class FakePromptModel:
    def __init__(self):
        self.prompt_calls = 0
        self.generate_calls = 0

    def create_voice_clone_prompt(self, **kwargs):
        self.prompt_calls += 1
        return {"reference": kwargs}

    def generate_voice_clone(self, **kwargs):
        import numpy as np

        self.generate_calls += 1
        return [np.array([0.0, 0.25, -0.25], dtype=np.float32)], 24000


class M41QwenJarvisVoiceTests(unittest.TestCase):
    def test_release_defaults_to_remote_qwen_and_clean_filter(self):
        defaults = VoiceProxyConfig()
        self.assertEqual(defaults.engine, "qwen_1_7b")
        self.assertEqual(defaults.qwen_filter, "clean")
        self.assertEqual(defaults.qwen_port, 10400)
        service = _voice_info("qwen_1_7b", ready=True).data["tts"][0]
        self.assertEqual(service["voices"][0]["name"], "jarvis_qwen")
        self.assertIn("Qwen3-TTS", service["description"])

    def test_addon_options_load_qwen_connection_and_filter(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "options.json"
            path.write_text(json.dumps({
                "engine": "qwen_1_7b",
                "qwen_host": "jarvis-ai.local",
                "qwen_port": 10401,
                "qwen_filter": "synthesized",
                "qwen_filter_strength": 0.62,
            }), encoding="utf-8")
            loaded = load_config(path)
        self.assertEqual(loaded.qwen_host, "jarvis-ai.local")
        self.assertEqual(loaded.qwen_port, 10401)
        self.assertEqual(loaded.qwen_filter, "synthesized")
        self.assertEqual(loaded.qwen_filter_strength, 0.62)

    def test_synthesized_filter_is_bounded_and_distinct(self):
        self.assertIn("synthesized", PROFILES)
        values = [round(9000 * ((index % 41) / 20 - 1)) for index in range(2400)]
        pcm = struct.pack(f"<{len(values)}h", *values)
        synthesized = process_voice_pcm16(pcm, 24000, 1, "synthesized", 0.55, 0.98)
        metallic = process_voice_pcm16(pcm, 24000, 1, "metallic", 0.55, 0.98)
        self.assertNotEqual(synthesized, pcm)
        self.assertNotEqual(synthesized, metallic)
        decoded = struct.unpack(f"<{len(synthesized) // 2}h", synthesized)
        self.assertLessEqual(max(decoded), 32767)
        self.assertGreaterEqual(min(decoded), -32768)

    def test_worker_caches_private_reference_prompt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audio = root / "reference.wav"
            transcript = root / "reference.txt"
            audio.write_bytes(b"private-audio-placeholder")
            transcript.write_text("Exact private reference transcript.", encoding="utf-8")
            model = FakePromptModel()
            engine = QwenVoiceEngine(QwenConfig(
                reference_audio=str(audio), reference_text_file=str(transcript)
            ), model_factory=lambda: model)
            asyncio.run(engine.warmup())
            pcm, rate = engine._generate_sync("Systems ready.")
            engine._generate_sync("All systems normal.")
        self.assertTrue(engine.ready)
        self.assertEqual(model.prompt_calls, 1)
        self.assertEqual(model.generate_calls, 2)
        self.assertEqual(rate, 24000)
        self.assertEqual(len(pcm), 6)

    def test_worker_segments_long_text_without_losing_words(self):
        text = (
            "Certainly, Benny. I have reviewed the current conditions throughout "
            "the house. Everything is operating normally, and no immediate action "
            "is required. The temperature is 21.5 degrees."
        )
        segments = split_segments(text, 100)
        self.assertEqual(len(segments), 4)
        self.assertEqual(" ".join(segments), text)
        self.assertIn("21.5", segments[-1])

    def test_private_reference_is_mounted_not_published(self):
        compose = (WORKER / "docker-compose.example.yaml").read_text(encoding="utf-8")
        self.assertIn("./private:/data/private:ro", compose)
        self.assertFalse((WORKER / "reference.wav").exists())
        config = (ADDON / "config.yaml").read_text(encoding="utf-8")
        self.assertIn('version: "0.32.0"', config)

    def test_home_assistant_cpu_worker_is_private_and_float32(self):
        addon = ROOT / "home_assistant" / "addons" / "jarvis_qwen_voice"
        entrypoint = (addon / "addon_entrypoint.py").read_text(encoding="utf-8")
        self.assertIn('device="cpu"', entrypoint)
        self.assertIn('dtype="float32"', entrypoint)
        self.assertIn('options.get("cpu_threads", 6)', entrypoint)
        config = (addon / "config.yaml").read_text(encoding="utf-8")
        self.assertIn("share:ro", config)
        self.assertIn("10400/tcp", config)
        self.assertFalse((addon / "qwen-reference.wav").exists())
        dockerfile = (addon / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("PYTHONPATH=/app", dockerfile)
        engine = (addon / "app" / "qwen_engine.py").read_text(encoding="utf-8")
        self.assertIn("snapshot_download", engine)
        self.assertIn('speech_tokenizer" / "preprocessor_config.json', engine)

    def test_home_assistant_worker_matches_deployable_worker(self):
        addon_app = ROOT / "home_assistant" / "addons" / "jarvis_qwen_voice" / "app"
        for name in ("protocol.py", "qwen_engine.py", "server.py"):
            self.assertEqual(
                (addon_app / name).read_bytes(),
                (WORKER / name).read_bytes(),
            )


if __name__ == "__main__":
    unittest.main()
