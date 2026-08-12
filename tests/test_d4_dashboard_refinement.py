import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "home_assistant" / "jarvis_ui" / "www" / "jarvis" / "jarvis-ui.js"


class D4DashboardRefinementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = SCRIPT.read_text(encoding="utf-8")

    def test_touch_and_cover_controls(self):
        self.assertIn("width:52px;height:52px", self.script)
        self.assertIn("width:56px;height:56px", self.script)
        cover = self.script.split("class JarvisCoverCard", 1)[1].split("class JarvisMediaCard", 1)[0]
        self.assertNotIn('data-service="stop_cover"', cover)
        self.assertIn("repeat(2,1fr)", cover)

    def test_real_bounded_history(self):
        sensor = self.script.split("class JarvisSensorCard", 1)[1].split("class JarvisSecurityCard", 1)[0]
        self.assertIn("history/period/", sensor)
        self.assertIn("IntersectionObserver", sensor)
        self.assertIn("MAX_HISTORY_SAMPLES", sensor)
        self.assertNotIn("Array.from({ length: 18 }", sensor)

    def test_washer_minutes_and_progress(self):
        washer = self.script.split("class JarvisWasherCard", 1)[1].split("class JarvisSpotifyCard", 1)[0]
        for token in ("remaining_entity", "total_cycle_entity", "total_cycle_minutes", "min", "% complete"):
            self.assertIn(token, washer)

    def test_new_editor_compatible_cards(self):
        for card in (
            "jarvis-calendar-card", "jarvis-glance-card", "jarvis-alerts-card",
            "jarvis-network-card", "jarvis-climate-overview-card",
            "jarvis-perimeter-card", "jarvis-energy-flow-card",
        ):
            self.assertIn(f'["{card}"', self.script)
        self.assertEqual(self.script.split("const CARD_DEFINITIONS", 1)[1].split("const CARD_DOMAINS", 1)[0].count('["jarvis-'), 41)

    def test_global_icons_and_performance_guards(self):
        for icon in ("calendar", "appointment", "storage", "leak", "smoke", "door", "window", "solar", "grid", "alert"):
            self.assertIn(f"  {icon}:", self.script)
        self.assertIn("window.customIconsets.jarvis", self.script)
        self.assertIn("DATA_CACHE_TTL", self.script)
        self.assertIn("CALENDAR_CACHE", self.script)


if __name__ == "__main__":
    unittest.main()
