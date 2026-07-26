import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jarvis.core.config_loader import ConfigLoader


class ConfigLoaderTests(unittest.TestCase):
    def test_uses_explicit_runtime_configuration_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "general.yaml").write_text("project:\n  name: Jarvis\n")
            with patch.dict(os.environ, {"JARVIS_CONFIG_DIR": directory}):
                loader = ConfigLoader()
                self.assertEqual(loader.config_folder, Path(directory).resolve())
                self.assertEqual(loader.load()["project"]["name"], "Jarvis")

    def test_merges_durable_home_access_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "general.yaml").write_text("home_assistant:\n  allowed_read_entities: []\n")
            policy = folder / "policy.yaml"
            policy.write_text("home_assistant:\n  allowed_read_entities: [camera.porch_camera]\n")
            with patch.dict(os.environ, {"JARVIS_CONFIG_DIR": directory, "JARVIS_HOME_POLICY_PATH": str(policy)}):
                self.assertEqual(ConfigLoader().load()["home_assistant"]["allowed_read_entities"], ["camera.porch_camera"])
