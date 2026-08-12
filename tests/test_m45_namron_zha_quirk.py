import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QUIRK = ROOT / "home_assistant" / "zha_quirks" / "namron_4512751.py"
DOCS = ROOT / "home_assistant" / "zha_quirks" / "README.md"


class NamronZhaQuirkTests(unittest.TestCase):
    def test_quirk_is_valid_python_and_exactly_matched(self):
        source = QUIRK.read_text(encoding="utf-8")
        ast.parse(source)
        self.assertIn('QuirkBuilder("NamronAS", "4512751")', source)
        self.assertIn(".replaces(Namron4512751OnOff)", source)
        self.assertIn(".replaces(Namron4512751LevelControl)", source)

    def test_commands_skip_only_the_missing_application_reply(self):
        source = QUIRK.read_text(encoding="utf-8")
        self.assertIn("expect_reply=False", source)
        self.assertIn("disable_default_response=True", source)
        self.assertIn("await super().command", source)
        self.assertIn("foundation.Status.SUCCESS", source)

    def test_home_assistant_installation_and_rollback_are_documented(self):
        docs = DOCS.read_text(encoding="utf-8")
        self.assertIn("/config/custom_zha_quirks", docs)
        self.assertIn("custom_quirks_path", docs)
        self.assertIn("restart Home Assistant", docs)
        self.assertIn("Rollback", docs)


if __name__ == "__main__":
    unittest.main()
