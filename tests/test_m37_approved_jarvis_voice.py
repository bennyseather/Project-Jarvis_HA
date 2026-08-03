import hashlib
import json
import struct
import sys
import tempfile
import unittest
import wave
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / "home_assistant" / "addons" / "jarvis_voice"
sys.path.insert(0, str(ADDON / "app"))
sys.path.insert(0, str(ADDON))

from addon_entrypoint import load_config  # noqa: E402
from chatterbox_engine import ChatterboxConfig, ChatterboxNanoEngine  # noqa: E402
from dsp import process_voice_pcm16, tighten_pauses_pcm16  # noqa: E402
from server import VoiceProxyConfig, _voice_info  # noqa: E402


class M37ApprovedJarvisVoiceTests(unittest.TestCase):
    def test_chatterbox_uses_normalized_reference_without_float64_conversion(self):
        class FakeModel:
            def __init__(self):
                self.calls = []

            def prepare_conditionals(self, path, **options):
                self.calls.append((path, options))

        reference = ADDON / "assets" / "jarvis-v5-reference.wav"
        model = FakeModel()
        engine = ChatterboxNanoEngine(
            ChatterboxConfig(reference_path=str(reference)),
            model_factory=lambda: model,
        )
        engine._prepare_conditioning()
        engine._prepare_conditioning()
        self.assertEqual(len(model.calls), 1)
        self.assertEqual(model.calls[0][0], str(reference))
        self.assertIs(model.calls[0][1]["norm_loudness"], False)

    def test_reference_is_bundled_clean_pcm(self):
        reference = ADDON / "assets" / "jarvis-v5-reference.wav"
        self.assertEqual(
            hashlib.sha256(reference.read_bytes()).hexdigest(),
            "e549400dacffe42b80eb26fc1cb45d0cf39af83297f46ea261ae54de7d257e96",
        )
        with wave.open(str(reference), "rb") as audio:
            self.assertEqual(audio.getnchannels(), 1)
            self.assertEqual(audio.getsampwidth(), 2)
            self.assertEqual(audio.getframerate(), 24000)
            duration = audio.getnframes() / audio.getframerate()
            self.assertGreater(duration, 7.0)
            self.assertLess(duration, 8.0)

    def test_pause_tightening_is_bounded_and_preserves_speech(self):
        rate = 16000
        tone = [5000] * round(rate * 0.12)
        silence = [0] * round(rate * 0.20)
        samples = tone + silence + tone
        pcm = struct.pack(f"<{len(samples)}h", *samples)
        tightened = tighten_pauses_pcm16(
            pcm, rate, maximum_pause_ms=25.0, minimum_silence_ms=100.0
        )
        decoded = struct.unpack(f"<{len(tightened) // 2}h", tightened)
        self.assertEqual(decoded[: len(tone)], tuple(tone))
        self.assertEqual(decoded[-len(tone):], tuple(tone))
        self.assertEqual(len(decoded), len(tone) * 2 + round(rate * 0.025))

    def test_v5_chain_is_deterministic_bounded_and_distinct(self):
        samples = [round(12000 * ((index % 37) / 18 - 1)) for index in range(2400)]
        pcm = struct.pack(f"<{len(samples)}h", *samples)
        first = process_voice_pcm16(pcm, 24000, 1, "jarvis_v5", 1.0, 0.98, 25.0)
        second = process_voice_pcm16(pcm, 24000, 1, "jarvis_v5", 1.0, 0.98, 25.0)
        self.assertEqual(first, second)
        self.assertNotEqual(first, pcm)
        decoded = struct.unpack(f"<{len(first) // 2}h", first)
        self.assertLessEqual(max(decoded), 32767)
        self.assertGreaterEqual(min(decoded), -32768)

    def test_legacy_defaults_migrate_without_overriding_custom_profiles(self):
        legacy = {
            "profile": "metallic",
            "strength": 0.92,
            "output_gain": 0.92,
            "pitch_factor": 1.10,
        }
        custom = dict(legacy, profile="clean")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "options.json"
            path.write_text(json.dumps(legacy), encoding="utf-8")
            migrated = load_config(path)
            self.assertEqual(migrated.profile, "jarvis_v5")
            self.assertEqual(migrated.strength, 1.0)
            self.assertEqual(migrated.staccato_pause_ms, 25.0)
            path.write_text(json.dumps(custom), encoding="utf-8")
            retained = load_config(path)
            self.assertEqual(retained.profile, "clean")

    def test_release_defaults_and_fallback_contract(self):
        config = (ADDON / "config.yaml").read_text(encoding="utf-8")
        dockerfile = (ADDON / "Dockerfile").read_text(encoding="utf-8")
        docs = (ADDON / "DOCS.md").read_text(encoding="utf-8")
        defaults = VoiceProxyConfig()
        self.assertEqual(defaults.profile, "jarvis_v5")
        self.assertEqual(defaults.staccato_pause_ms, 25.0)
        self.assertIn('version: "0.29.0"', config)
        self.assertIn('profile: "jarvis_v5"', config)
        self.assertIn("COPY assets/jarvis-v5-reference.wav", dockerfile)
        self.assertIn("Kokoro", docs)
        self.assertIn("Piper", docs)
        service = _voice_info("chatterbox_nano").data["tts"][0]
        self.assertEqual(service["version"], "0.29.0")


if __name__ == "__main__":
    unittest.main()
