import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / "home_assistant" / "addons" / "jarvis_voice"
sys.path.insert(0, str(ADDON / "app"))
sys.path.insert(0, str(ADDON))

from addon_entrypoint import load_config  # noqa: E402
from chatterbox_engine import articulation_options, split_spoken_segments  # noqa: E402
from dsp import darken_voice_pcm16  # noqa: E402
from server import VoiceProxyConfig, _voice_info  # noqa: E402


class M38ResponsiveArticulateVoiceTests(unittest.TestCase):
    def test_long_reply_splits_at_natural_clauses_and_is_lossless(self):
        text = (
            "The main floor is secure, all exterior doors are locked, and the "
            "temperature is 21.5 degrees. Dr. Smith arrives at 10.30 tomorrow."
        )
        segments = split_spoken_segments(text, 72)
        self.assertGreaterEqual(len(segments), 3)
        self.assertEqual(" ".join(segments), text)
        self.assertTrue(all(len(segment) <= 72 for segment in segments))
        self.assertIn("21.5", " ".join(segments))
        self.assertIn("Dr. Smith", " ".join(segments))

    def test_crisp_generation_is_more_conservative_than_balanced(self):
        crisp = articulation_options("crisp")
        balanced = articulation_options("balanced")
        self.assertLess(crisp["temperature"], balanced["temperature"])
        self.assertGreater(crisp["repetition_penalty"], balanced["repetition_penalty"])
        self.assertNotIn("audio_prompt_path", crisp)

    def test_darkening_is_bounded_subtle_and_deterministic(self):
        samples = [10000 if index % 2 else -10000 for index in range(1000)]
        pcm = struct.pack(f"<{len(samples)}h", *samples)
        dark = darken_voice_pcm16(pcm, 24000, 0.10)
        self.assertEqual(dark, darken_voice_pcm16(pcm, 24000, 0.10))
        self.assertNotEqual(dark, pcm)
        decoded = struct.unpack(f"<{len(dark) // 2}h", dark)
        self.assertLessEqual(max(decoded), 32767)
        self.assertGreaterEqual(min(decoded), -32768)

    def test_v5_defaults_migrate_darker_without_overwriting_custom_pitch(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "options.json"
            path.write_text(json.dumps({
                "profile": "jarvis_v5", "pitch_factor": 1.055,
                "voice_revision": 5,
            }), encoding="utf-8")
            migrated = load_config(path)
            self.assertEqual(migrated.pitch_factor, 1.035)
            self.assertEqual(migrated.darkness, 0.10)
            path.write_text(json.dumps({
                "profile": "jarvis_v5", "pitch_factor": 1.02,
                "voice_revision": 5,
            }), encoding="utf-8")
            custom = load_config(path)
            self.assertEqual(custom.pitch_factor, 1.02)

    def test_release_defaults_and_diagnostics(self):
        config_text = (ADDON / "config.yaml").read_text(encoding="utf-8")
        defaults = VoiceProxyConfig()
        self.assertEqual(defaults.articulation_mode, "crisp")
        self.assertEqual(defaults.maximum_segment_characters, 105)
        self.assertEqual(defaults.darkness, 0.10)
        self.assertIn('version: "0.32.0"', config_text)
        self.assertIn("maximum_segment_characters: 105", config_text)
        status = _voice_info(
            "chatterbox_nano", conditioning_seconds=1.2,
            warmup_seconds=2.4, last_first_audio_seconds=3.1,
        ).data["tts"][0]["jarvis_status"]
        self.assertEqual(status["conditioning_seconds"], 1.2)
        self.assertEqual(status["last_first_audio_seconds"], 3.1)


if __name__ == "__main__":
    unittest.main()
