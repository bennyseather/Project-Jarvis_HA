import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).parents[1]
UI_ROOT = ROOT / "home_assistant" / "jarvis_ui"


class JarvisCommandCenterTests(unittest.TestCase):
    def test_dashboard_has_five_native_sections_views(self):
        dashboard = yaml.safe_load(
            (UI_ROOT / "jarvis-dashboard.yaml").read_text(encoding="utf-8")
        )
        views = dashboard["views"]
        self.assertEqual(
            [view["path"] for view in views],
            ["command", "rooms", "environment", "media-voice", "jarvis"],
        )
        self.assertTrue(all(view["type"] == "sections" for view in views))
        serialized = (UI_ROOT / "jarvis-dashboard.yaml").read_text(
            encoding="utf-8"
        )
        self.assertEqual(serialized.count("custom:jarvis-voice-card"), 3)
        self.assertEqual(serialized.count("custom:jarvis-action-card"), 3)
        self.assertNotIn("http://", serialized)
        self.assertNotIn("https://", serialized)
        self.assertIn("start_listening: true", serialized)

    def test_theme_and_assets_are_complete(self):
        themes = yaml.safe_load(
            (UI_ROOT / "themes" / "jarvis-command-center.yaml").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            set(themes),
            {"Jarvis Command Center", "Jarvis Command Center Panel"},
        )
        for asset in (
            "jarvis-command-center-landscape.png",
            "jarvis-command-center-portrait.png",
        ):
            path = UI_ROOT / "www" / "jarvis" / asset
            self.assertTrue(path.is_file())
            self.assertGreater(path.stat().st_size, 100_000)
        self.assertGreater(
            (UI_ROOT / "jarvis-command-center-preview.png").stat().st_size,
            100_000,
        )

    def test_interactive_cards_are_local_accessible_and_policy_bounded(self):
        script = (
            UI_ROOT / "www" / "jarvis" / "jarvis-voice-card.js"
        ).read_text(encoding="utf-8")
        self.assertIn('import "./jarvis-ui.js"', script)
        design_system = (
            UI_ROOT / "www" / "jarvis" / "jarvis-ui.js"
        ).read_text(encoding="utf-8")
        self.assertIn('customElements.define(tag, klass)', design_system)
        self.assertIn('action: "assist"', design_system)
        self.assertIn('pipeline_id: this._config.pipeline_id', design_system)
        self.assertIn('event.key === "Enter"', design_system)
        self.assertIn('event.key === " "', design_system)
        self.assertIn("prefers-reduced-motion:reduce", design_system)
        self.assertNotIn("callApi(", design_system)
        self.assertNotIn("callWS(", design_system)
        self.assertNotIn("fetch(", design_system)

    def test_configuration_snippet_registers_sidebar_dashboard(self):
        snippet = (UI_ROOT / "configuration-snippet.yaml").read_text(
            encoding="utf-8"
        )
        self.assertIn("themes: !include_dir_merge_named themes", snippet)
        self.assertIn("jarvis-command-center:", snippet)
        self.assertIn("show_in_sidebar: true", snippet)
        readme = (UI_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(
            "/local/jarvis/jarvis-ui.js?v=0.9.4",
            readme,
        )


if __name__ == "__main__":
    unittest.main()
