"""
Configuration loader for Project Jarvis.
"""

from pathlib import Path
import os

import yaml


class ConfigLoader:
    """
    Loads and manages application configuration.
    """

    def __init__(self):
        current_file = Path(__file__).resolve()

        self.project_root = current_file.parents[3]
        configured_folder = os.environ.get("JARVIS_CONFIG_DIR")
        self.config_folder = (
            Path(configured_folder).resolve()
            if configured_folder
            else self.project_root / "config"
        )
        self.config = {}

    def load(self):
        """
        Load all configuration files.
        """

        self.config = self._load_yaml("general.yaml")

        secrets_file = self.config_folder / "secrets.yaml"

        if secrets_file.exists():
            secrets = self._load_yaml("secrets.yaml")
            self._merge(self.config, secrets)

        policy_path = os.environ.get("JARVIS_HOME_POLICY_PATH")
        if policy_path:
            policy_file = Path(policy_path)
            if not policy_file.exists():
                raise FileNotFoundError(f"Home access policy is missing: {policy_file}")
            with policy_file.open("r", encoding="utf-8") as file:
                policy = yaml.safe_load(file) or {}
            if not isinstance(policy, dict) or "home_assistant" not in policy:
                raise ValueError("Home access policy must contain a home_assistant mapping.")
            self._merge(self.config, policy)

        return self.config

    def _load_yaml(self, filename: str):
        """
        Load a single YAML file.
        """

        file = self.config_folder / filename

        with open(file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _merge(self, target: dict, source: dict):
        """
        Merge two dictionaries recursively.
        """

        for key, value in source.items():

            if (
                key in target
                and isinstance(target[key], dict)
                and isinstance(value, dict)
            ):
                self._merge(target[key], value)

            else:
                target[key] = value
