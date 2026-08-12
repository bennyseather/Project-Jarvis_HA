import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jarvis.learning.adaptive_preferences import (
    AdaptiveLearningPolicy,
    AdaptivePreference,
    AdaptivePreferenceController,
    SQLiteAdaptivePreferenceStore,
)
from jarvis.homeassistant.conversation_bridge import JarvisConversationBridge


class M46AdaptivePreferenceLearningTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.now = datetime(2026, 8, 12, 12, tzinfo=timezone.utc)
        self.store = SQLiteAdaptivePreferenceStore(Path(self.directory.name) / "jarvis.db")
        self.controller = AdaptivePreferenceController(
            self.store, AdaptiveLearningPolicy(), clock=lambda: self.now
        )

    def tearDown(self):
        self.store.close()
        self.directory.cleanup()

    def test_repetition_automatically_approves_on_third_observation(self):
        first = self.controller.handle("I prefer the office at 21 degrees", "c1")
        second = self.controller.handle("I prefer the office at 21 degrees", "c1")
        third = self.controller.handle("I prefer the office at 21 degrees", "c1")
        self.assertIn("1 of 3", first["message"])
        self.assertIn("2 of 3", second["message"])
        self.assertEqual(third["status"], "success")
        self.assertIn("automatically approved", third["message"])
        self.assertEqual(self.controller.context()[0]["value"], "21.0")

    def test_equivalent_temperature_wording_stays_in_adaptive_learning(self):
        self.controller.set_area_references(("upstairs office", "living room"))
        self.controller.handle("I prefer the upstairs office at 21 degrees", "c1")
        self.controller.handle("I prefer the upstairs office at 21 degrees", "c1")
        result = self.controller.handle(
            "I like the upstairs office temperature to be 21 degrees", "c1"
        )
        self.assertIn("automatically approved", result["message"])
        item = self.store.list()[0]
        self.assertEqual(item.evidence_count, 3)
        self.assertEqual(item.key, "temperature.upstairs_office")

    def test_all_ha_areas_use_canonical_names_and_ambiguous_partial_names_do_not_merge(self):
        self.controller.set_area_references(
            ("upstairs office", "living room", "guest bedroom"),
            {"lounge": "living room"},
        )
        self.controller.handle("I prefer my office at 21 degrees", "c1")
        self.controller.handle("I prefer the upstairs office at 21 degrees", "c1")
        result = self.controller.handle("I like office temperature to be 21 degrees", "c1")
        self.assertIn("automatically approved", result["message"])
        self.assertEqual(self.store.list()[0].key, "temperature.upstairs_office")
        for phrase in ("the living room", "my lounge", "living room area"):
            self.controller.handle(f"I prefer {phrase} at 20 degrees", "c2")
        self.assertEqual(self.store.get_by_key("temperature.living_room").status, "approved")

    def test_existing_article_and_possessive_scopes_migrate_to_area(self):
        timestamp = self.now.isoformat()
        self.store.save(AdaptivePreference(
            "one", "temperature.my_office", "temperature", "my_office", "21.0",
            3, 0.95, "approved", timestamp, timestamp, ("first",),
        ))
        self.store.save(AdaptivePreference(
            "two", "temperature.office", "temperature", "office", "21.0",
            1, 0.55, "observed", timestamp, timestamp, ("second",),
        ))
        self.assertEqual(len(self.store.list()), 2)
        self.controller.set_area_references(("upstairs office",))
        self.assertEqual(len(self.store.list()), 1)
        item = self.store.list()[0]
        self.assertEqual(item.key, "temperature.upstairs_office")
        self.assertEqual(item.status, "approved")

    def test_restart_persistence_explanation_correction_and_deletion(self):
        for _ in range(3):
            self.controller.handle("I prefer the lounge at 20 degrees", "c1")
        replacement = AdaptivePreferenceController(self.store, AdaptiveLearningPolicy(), clock=lambda: self.now)
        self.assertIn("lounge", replacement.handle("What have you learned?", "c2")["message"])
        self.assertIn("3 times", replacement.handle("Why did you learn lounge temperature?", "c2")["message"])
        replacement.handle("I prefer the lounge at 20 degrees", "c2")
        corrected = replacement.handle("That is wrong, use 21 degrees instead", "c2")
        self.assertIn("Correction recorded", corrected["message"])
        self.assertEqual(replacement.context(), ())
        forgotten = replacement.handle("Forget the lounge temperature preference", "c2")
        self.assertEqual(forgotten["status"], "success")
        self.assertEqual(self.store.list(), ())

    def test_forbidden_categories_and_stale_observation_decay(self):
        denied = self.controller.handle("I prefer the front door unlock at 21 degrees", "c1")
        self.assertEqual(denied["status"], "forbidden")
        self.controller.handle("I prefer the office at 21 degrees", "c1")
        self.now += timedelta(days=91)
        self.controller.context()
        item = self.store.list()[0]
        self.assertEqual(item.evidence_count, 0)
        self.assertEqual(item.status, "stale")

    def test_repeated_successful_actions_auto_approve_but_failures_cannot(self):
        for _ in range(2):
            self.assertIsNone(self.controller.observe_outcome(
                "Set the office temperature to 21 degrees",
                {"status": "action_done"},
                "c1",
            ))
        proposal = self.controller.observe_outcome(
            "Set the office temperature to 21 degrees",
            {"status": "success"},
            "c1",
        )
        self.assertIsNone(proposal)
        self.assertEqual(self.controller.context()[0]["value"], "21.0")
        before = len(self.store.list())
        self.controller.observe_outcome(
            "Set lounge lights to 40 percent", {"status": "unavailable"}, "c1"
        )
        self.assertEqual(len(self.store.list()), before)

    def test_policy_validation(self):
        with self.assertRaises(ValueError):
            AdaptiveLearningPolicy.from_config({"evidence_threshold": 1})
        with self.assertRaises(ValueError):
            AdaptiveLearningPolicy.from_config({"minimum_confidence": 0.2})
        self.assertIn("approved", JarvisConversationBridge._AFFIRMATIVE)


if __name__ == "__main__":
    unittest.main()
