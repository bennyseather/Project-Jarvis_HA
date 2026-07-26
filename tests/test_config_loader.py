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
