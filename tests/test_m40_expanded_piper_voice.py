import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / "home_assistant" / "addons" / "jarvis_voice"
sys.path.insert(0, str(ADDON / "app"))
sys.path.insert(0, str(ADDON))

from addon_entrypoint import load_config  # noqa: E402
from server import VoiceProxyConfig, _voice_info  # noqa: E402


class M40ExpandedPiperVoiceTests(unittest.TestCase):
    def test_release_defaults_to_m40(self):
        defaults = VoiceProxyConfig(engine="piper_m40")
        self.assertEqual(defaults.engine, "piper_m40")
        self.assertEqual(
            defaults.model_package,
            "/share/jarvis_voice/jarvis-piper-m40.zip",
        )
        service = _voice_info("piper_m40", ready=True).data["tts"][0]
        self.assertEqual(service["version"], "0.34.3")
        self.assertEqual(service["voices"][0]["name"], "jarvis_m40")
        self.assertTrue(service["voices"][0]["installed"])

    def test_untouched_m39_defaults_migrate_to_m40(self):
        with tempfile.TemporaryDirectory() as directory:
            options = Path(directory) / "options.json"
            options.write_text(json.dumps({
                "engine": "piper_m39",
                "model_package": "/share/jarvis_voice/jarvis-piper-m39.zip",
                "model_cache_dir": "/data/models/m39",
                "voice_revision": 7,
            }), encoding="utf-8")
            migrated = load_config(options)
            self.assertEqual(migrated.engine, "piper_m40")
            self.assertEqual(
                migrated.model_package,
                "/share/jarvis_voice/jarvis-piper-m40.zip",
            )
            self.assertEqual(migrated.model_cache_dir, "/data/models/m40")

    def test_custom_m39_location_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            options = Path(directory) / "options.json"
            options.write_text(json.dumps({
                "engine": "piper_m39",
                "model_package": "/share/private/m39.zip",
                "model_cache_dir": "/data/private-m39",
                "voice_revision": 7,
            }), encoding="utf-8")
            loaded = load_config(options)
            self.assertEqual(loaded.engine, "piper_m39")
            self.assertEqual(loaded.model_package, "/share/private/m39.zip")
            self.assertEqual(loaded.model_cache_dir, "/data/private-m39")

    def test_private_training_material_is_not_tracked(self):
        tracked = subprocess.run(
            ["git", "ls-files", "training/m40_dataset", "training/m40_models"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        self.assertEqual(tracked, "")


if __name__ == "__main__":
    unittest.main()
