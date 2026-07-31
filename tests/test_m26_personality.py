import unittest

from jarvis.knowledge.in_memory_store import InMemoryKnowledgeStore
from jarvis.persona import DEFAULT_PERSONA
from jarvis.personality import PersonalityManager


class M26PersonalityTests(unittest.TestCase):
    def setUp(self):
        self.store = InMemoryKnowledgeStore()
        self.manager = PersonalityManager(self.store)

    def test_baseline_is_original_british_and_safety_subordinate(self):
        instructions = DEFAULT_PERSONA.model_instructions()
        self.assertIn("British English", instructions)
        self.assertIn("subtly synthetic", instructions)
        self.assertIn("never overrides", instructions)
        self.assertIn("Do not quote, impersonate", instructions)

    def test_preferences_are_inspectable_adjustable_and_resettable(self):
        self.assertEqual(
            self.manager.handle("address me as Benny")["status"], "success"
        )
        self.manager.handle("set personality humour off")
        self.manager.handle("set personality verbosity balanced")
        profile = self.manager.profile()
        self.assertEqual(profile.address, "Benny")
        self.assertEqual(profile.humour, "off")
        self.assertEqual(profile.verbosity, "balanced")
        self.assertIn("Benny", self.manager.handle("show personality")["message"])
        self.manager.handle("reset personality")
        self.assertEqual(self.manager.profile().address, "")
        self.assertEqual(self.store.list_records(), ())

    def test_invalid_preference_requires_clarification(self):
        result = self.manager.handle("set personality humour extreme")
        self.assertEqual(result["status"], "clarification_required")

    def test_runtime_and_addon_mirror_include_personality(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        application = (root / "src/jarvis/core/application.py").read_text()
        self.assertIn("personality_manager.profile().context()", application)
        self.assertTrue(
            (root / "home_assistant/addons/jarvis/app/src/jarvis/personality.py").exists()
        )


if __name__ == "__main__":
    unittest.main()
