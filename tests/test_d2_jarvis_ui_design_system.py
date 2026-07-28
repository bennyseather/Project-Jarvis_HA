import json
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).parents[1]
UI_ROOT = ROOT / "home_assistant" / "jarvis_ui"
SCRIPT = UI_ROOT / "www" / "jarvis" / "jarvis-ui.js"


class JarvisUIDesignSystemTests(unittest.TestCase):
    def setUp(self):
        self.script = SCRIPT.read_text(encoding="utf-8")

    def test_complete_visual_card_set_is_registered(self):
        expected = {
            "jarvis-button-card",
            "jarvis-action-card",
            "jarvis-entity-card",
            "jarvis-light-card",
            "jarvis-switch-card",
            "jarvis-slider-card",
            "jarvis-climate-card",
            "jarvis-cover-card",
            "jarvis-media-card",
            "jarvis-camera-card",
            "jarvis-sensor-card",
            "jarvis-security-card",
            "jarvis-status-card",
            "jarvis-voice-card",
            "jarvis-icon-catalog-card",
            "jarvis-coverage-card",
        }
        for card in expected:
            self.assertIn(f'["{card}"', self.script)
        self.assertIn("window.customCards", self.script)
        # Most entity cards inherit the common visual form from JarvisBaseCard.
        self.assertGreaterEqual(self.script.count("getConfigForm()"), 7)
        self.assertIn("getEntitySuggestion", self.script)

    def test_hud_style_is_squared_responsive_and_accessible(self):
        self.assertIn("border-radius:2px", self.script)
        self.assertIn("clip-path:polygon", self.script)
        self.assertIn("ha-card.interactive:hover", self.script)
        self.assertIn("ha-card.interactive:focus-visible", self.script)
        self.assertIn("@media(max-width:680px)", self.script)
        self.assertIn("@media(prefers-reduced-motion:reduce)", self.script)
        self.assertIn('card.setAttribute("role", "button")', self.script)

        themes = yaml.safe_load(
            (UI_ROOT / "themes" / "jarvis-command-center.yaml").read_text(
                encoding="utf-8"
            )
        )
        for theme in themes.values():
            dark = theme["modes"]["dark"]
            self.assertEqual(dark["ha-card-border-radius"], "2px")
            self.assertEqual(dark["jarvis-cyan"], "#20D8FF")
            self.assertEqual(dark["jarvis-amber"], "#FFC247")

    def test_icon_set_is_original_bounded_and_has_safe_fallback(self):
        self.assertIn("window.customIconsets.jarvis", self.script)
        self.assertIn("ICON_PATHS", self.script)
        self.assertIn("ICON_ALIASES", self.script)
        alias_block = self.script.split("const ICON_ALIASES = {", 1)[1].split(
            "};", 1
        )[0]
        self.assertGreaterEqual(alias_block.count(":"), 50)
        for icon in (
            "lightbulb",
            "spotlight",
            "plug",
            "thermostat",
            "cover",
            "speaker",
            "camera",
            "battery",
            "vehicle",
            "automation",
        ):
            self.assertIn(icon, self.script)
        self.assertIn('|| state?.attributes?.icon ||', self.script)

    def test_control_calls_stay_inside_home_assistant_frontend(self):
        self.assertIn("this._hass.callService", self.script)
        self.assertNotIn("fetch(", self.script)
        self.assertNotIn("XMLHttpRequest", self.script)
        self.assertNotIn("WebSocket(", self.script)
        self.assertNotIn("localStorage", self.script)
        self.assertNotIn("sessionStorage", self.script)

    def test_catalog_and_coverage_are_local_and_bounded(self):
        catalog = yaml.safe_load(
            (UI_ROOT / "jarvis-component-catalog.yaml").read_text(
                encoding="utf-8"
            )
        )
        serialized = (UI_ROOT / "jarvis-component-catalog.yaml").read_text(
            encoding="utf-8"
        )
        self.assertEqual(catalog["views"][0]["path"], "components")
        self.assertIn("custom:jarvis-icon-catalog-card", serialized)
        self.assertIn("custom:jarvis-coverage-card", serialized)
        self.assertIn("Object.values(this._hass.states || {})", self.script)
        self.assertIn("slice(0, 12)", self.script)

    def test_camera_starts_live_and_voice_uses_shared_hud_framing(self):
        self.assertIn("window.loadCardHelpers()", self.script)
        self.assertIn('camera_view: "live"', self.script)
        self.assertIn('type: "picture-entity"', self.script)
        self.assertIn("camera_proxy/${this._config.entity}", self.script)
        self.assertIn("setInterval(refresh, 5000)", self.script)
        self.assertIn('class="voice-node"', self.script)
        self.assertIn("clip-path:polygon", self.script)
        self.assertIn('class="node-corner tl"', self.script)
        self.assertIn('class="node-corner br"', self.script)

    def test_hacs_distribution_matches_source(self):
        manifest = json.loads((UI_ROOT / "hacs.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "Project Jarvis UI")
        self.assertEqual(manifest["filename"], "Project-Jarvis_HA.js")
        distribution = UI_ROOT / "dist" / manifest["filename"]
        self.assertTrue(distribution.is_file())
        self.assertEqual(
            distribution.read_bytes(),
            SCRIPT.read_bytes(),
        )

    def test_release_documentation_has_visual_editor_and_boundaries(self):
        readme = (UI_ROOT / "README.md").read_text(encoding="utf-8")
        milestone = (
            ROOT / "docs" / "detours" / "D2-jarvis-ui-design-system.md"
        ).read_text(encoding="utf-8")
        self.assertIn("Add and edit cards visually", readme)
        self.assertIn("HACS is not required", readme)
        self.assertIn("Home Assistant owns entity state", milestone)
        self.assertIn("does not modify Jarvis memory", milestone)


if __name__ == "__main__":
    unittest.main()
