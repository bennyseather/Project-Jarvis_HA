import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).parents[1]
UI_ROOT = ROOT / "home_assistant" / "jarvis_ui"
SCRIPT = UI_ROOT / "www" / "jarvis" / "jarvis-ui.js"


class CompleteJarvisDashboardSystemTests(unittest.TestCase):
    def setUp(self):
        self.script = SCRIPT.read_text(encoding="utf-8")

    def test_registers_all_thirty_four_cards(self):
        definitions = self.script.split("const CARD_DEFINITIONS = [", 1)[1].split(
            "];", 1
        )[0]
        self.assertEqual(definitions.count('["jarvis-'), 41)
        for card in (
            "room", "presence", "weather", "energy", "fan", "vacuum", "lock",
            "alarm", "scene", "timer", "mower", "washer", "spotify",
            "ev-charger", "tile", "markup", "car",
        ):
            self.assertIn(f'["jarvis-{card}-card"', definitions)

    def test_new_cards_are_visual_editor_compatible(self):
        for class_name in (
            "JarvisRoomCard", "JarvisPresenceCard", "JarvisWeatherCard",
            "JarvisEnergyCard", "JarvisFanCard", "JarvisVacuumCard",
            "JarvisLockCard", "JarvisAlarmCard", "JarvisSceneCard",
            "JarvisTimerCard", "JarvisMowerCard", "JarvisWasherCard",
            "JarvisSpotifyCard", "JarvisEvChargerCard", "JarvisTileCard",
            "JarvisMarkupCard", "JarvisCarCard",
        ):
            self.assertIn(f"class {class_name}", self.script)
        self.assertIn("static getConfigForm()", self.script)
        self.assertIn("getEntitySuggestion", self.script)

    def test_numeric_telemetry_is_limited_to_one_decimal(self):
        self.assertIn("function formatValue(value)", self.script)
        self.assertIn("numeric.toFixed(1)", self.script)
        self.assertIn("formatState(state, { entity: id })", self.script)
        self.assertIn("formatValue(attrs.current_temperature)", self.script)

    def test_tokens_and_container_responsiveness_are_shared(self):
        self.assertIn("container-type:inline-size", self.script)
        self.assertIn("@container(max-width:430px)", self.script)
        theme = (UI_ROOT / "themes" / "jarvis-command-center.yaml").read_text(
            encoding="utf-8"
        )
        for token in (
            "jarvis-space-1", "jarvis-space-2", "jarvis-space-3",
            "jarvis-space-4", "jarvis-control-size",
        ):
            self.assertIn(token, theme)

    def test_weather_current_state_and_forecast_stay_synchronized(self):
        self.assertIn("const nextState = stateObject(value, this._config?.entity)", self.script)
        self.assertIn("const nextSignature = JSON.stringify([", self.script)
        self.assertIn("const stateChanged = nextSignature !== this._weatherSignature", self.script)
        self.assertIn("this._weatherSignature = nextSignature", self.script)
        self.assertIn("queueMicrotask(() => this._mountForecast())", self.script)
        self.assertIn("forecast_slots: Math.min(5, Math.max(3", self.script)
        self.assertIn('type: "weather-forecast"', self.script)

    def test_weather_status_is_rendered_once(self):
        weather = self.script.split(
            "class JarvisWeatherCard", 1
        )[1].split("class JarvisEnergyCard", 1)[0]
        self.assertNotIn('this.entityHeader("Weather channel")', weather)
        self.assertEqual(weather.count('String(state?.state || "unknown")'), 1)

    def test_jarvis_badges_register_with_visual_editors(self):
        for badge in ("entity", "shortcut", "progress", "presence"):
            self.assertIn(f'["jarvis-{badge}-badge"', self.script)
            self.assertIn(f'jarvis-{badge}-badge-editor', self.script)
        self.assertIn("window.customBadges", self.script)
        self.assertIn("static getConfigElement()", self.script)
        self.assertIn('"config-changed"', self.script)
        self.assertIn("form.schema = badgeFormSchema", self.script)
        self.assertIn('const form = this.shadowRoot.querySelector("ha-form")', self.script)
        self.assertIn("if (!form) this.render()", self.script)
        self.assertNotIn("if (form) form.hass = value", self.script)
        self.assertIn(
            'if (!this.shadowRoot.querySelector("ha-form")) this.render()',
            self.script,
        )
        self.assertIn("this._config = event.detail.value", self.script)

    def test_dashboard_is_room_based_and_catalog_is_complete(self):
        dashboard = yaml.safe_load(
            (UI_ROOT / "jarvis-dashboard.yaml").read_text(encoding="utf-8")
        )
        paths = [view["path"] for view in dashboard["views"]]
        self.assertIn("rooms", paths)
        self.assertIn("upstairs-office", paths)
        self.assertTrue(
            next(view for view in dashboard["views"]
                 if view["path"] == "upstairs-office")["subview"]
        )
        catalog = (UI_ROOT / "jarvis-component-catalog.yaml").read_text(
            encoding="utf-8"
        )
        for card in ("room", "mower", "washer", "spotify", "ev-charger", "markup", "car"):
            self.assertIn(f"custom:jarvis-{card}-card", catalog)

    def test_d3_preserves_frontend_privacy_boundary(self):
        self.assertNotIn("fetch(", self.script)
        self.assertNotIn("XMLHttpRequest", self.script)
        self.assertNotIn("WebSocket(", self.script)
        self.assertNotIn("localStorage", self.script)
        self.assertNotIn("sessionStorage", self.script)


if __name__ == "__main__":
    unittest.main()
