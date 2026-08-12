import asyncio
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import zipfile


ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / "home_assistant" / "addons" / "jarvis_voice"
sys.path.insert(0, str(ADDON / "app"))
sys.path.insert(0, str(ADDON))

from addon_entrypoint import load_config  # noqa: E402
from piper_m39_engine import (  # noqa: E402
    CONFIG_NAME,
    MODEL_NAME,
    PiperM39Config,
    PiperM39Engine,
)
from server import VoiceProxyConfig, _voice_info  # noqa: E402


class M39DedicatedPiperVoiceTests(unittest.TestCase):
    def _package(self, root: Path) -> Path:
        package = root / "jarvis-piper-m39.zip"
        with zipfile.ZipFile(package, "w") as archive:
            archive.writestr(MODEL_NAME, b"m" * 1_000_001)
            archive.writestr(CONFIG_NAME, json.dumps({"audio": {"sample_rate": 22050}}) + " " * 100)
        return package

    def test_private_package_is_validated_and_extracted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            engine = PiperM39Engine(PiperM39Config(
                package_path=str(self._package(root)),
                cache_dir=str(root / "cache"),
            ))
            engine._prepare_sync()
            self.assertTrue(engine.ready)
            self.assertTrue((root / "cache" / MODEL_NAME).is_file())
            self.assertTrue((root / "cache" / CONFIG_NAME).is_file())

    def test_synthesis_uses_local_raw_piper_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            engine = PiperM39Engine(PiperM39Config(
                package_path=str(self._package(root)),
                cache_dir=str(root / "cache"),
            ))
            engine._prepare_sync()
            completed = subprocess.CompletedProcess([], 0, stdout=b"\x01\x00" * 100, stderr=b"")
            with patch("piper_m39_engine.subprocess.run", return_value=completed) as run:
                pcm, rate = asyncio.run(engine.synthesize("Systems ready."))
            self.assertEqual(rate, 22050)
            self.assertEqual(pcm, completed.stdout)
            self.assertIn("--output-raw", run.call_args.args[0])
            self.assertIn("--noise-scale", run.call_args.args[0])
            self.assertIn("--noise-w", run.call_args.args[0])
            self.assertEqual(run.call_args.kwargs["input"], b"Systems ready.\n")

    def test_release_defaults_to_private_m39_engine(self):
        defaults = VoiceProxyConfig(engine="piper_m40")
        self.assertEqual(defaults.engine, "piper_m40")
        self.assertEqual(defaults.darkness, 0.10)
        service = _voice_info("piper_m39", ready=True).data["tts"][0]
        self.assertEqual(service["voices"][0]["name"], "jarvis_m39")
        self.assertTrue(service["voices"][0]["installed"])
        config = (ADDON / "config.yaml").read_text(encoding="utf-8")
        self.assertIn('version: "0.34.3"', config)
        self.assertIn("- share:ro", config)
        self.assertIn('engine: "qwen_1_7b"', config)

    def test_addon_options_preserve_private_model_location(self):
        with tempfile.TemporaryDirectory() as directory:
            options = Path(directory) / "options.json"
            options.write_text(json.dumps({
                "engine": "piper_m39",
                "model_package": "/share/private/model.zip",
                "model_cache_dir": "/data/private",
            }), encoding="utf-8")
            loaded = load_config(options)
            self.assertEqual(loaded.model_package, "/share/private/model.zip")
            self.assertEqual(loaded.model_cache_dir, "/data/private")
            self.assertEqual(loaded.piper_noise_scale, 0.35)
            self.assertEqual(loaded.piper_noise_w, 0.45)
            self.assertTrue(loaded.clarity_mode)

    def test_untouched_m38_defaults_migrate_but_custom_engine_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            options = Path(directory) / "options.json"
            options.write_text(json.dumps({
                "engine": "chatterbox_nano", "profile": "jarvis_v5",
                "strength": 1.0, "output_gain": 0.98,
                "pitch_factor": 1.035, "voice_revision": 6,
            }), encoding="utf-8")
            migrated = load_config(options)
            self.assertEqual(migrated.engine, "piper_m39")
            self.assertEqual(migrated.darkness, 0.12)
            options.write_text(json.dumps({
                "engine": "kokoro", "profile": "jarvis_v5",
                "voice_revision": 6,
            }), encoding="utf-8")
            self.assertEqual(load_config(options).engine, "kokoro")


if __name__ == "__main__":
    unittest.main()
