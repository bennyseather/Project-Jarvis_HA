"""
Configuration loader for Project Jarvis.
"""

from pathlib import Path

import yaml


class ConfigLoader:
    """
    Loads YAML configuration files.
    """

    def __init__(self):
        self.config_folder = Path("config")

    def load(self, filename: str):
        file = self.config_folder / filename

        with open(file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)