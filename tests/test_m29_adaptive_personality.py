import unittest

from jarvis.knowledge.in_memory_store import InMemoryKnowledgeStore
from jarvis.persona import DEFAULT_PERSONA
from jarvis.personality import PersonalityManager
from jarvis.personality_presentation import PersonalityPresenter


class M29AdaptivePersonalityTests(unittest.TestCase):
    def setUp(self):
        self.store = InMemoryKnowledgeStore()
        self.manager = PersonalityManager(self.store)
        self.presenter = PersonalityPresenter(self.manager)

    def test_complete_profile_is_explicit_inspectable_and_forgettable(self):
        self.manager.handle("address me as Benny", "c1")
        self.manager.handle("set personality humour moderate", "c1")
        self.manager.handle("set personality warmth warm", "c1")
        self.manager.handle("set personality verbosity detailed", "c1")
        profile = self.manager.profile()
        self.assertEqual(profile.address, "Benny")
        self.assertEqual(profile.humour, "moderate")
        self.assertEqual(profile.warmth, "warm")
        self.assertEqual(profile.verbosity, "detailed")
        shown = self.manager.handle("show relationship preferences", "c1")
        self.assertIn("Benny", shown["message"])
        self.assertIn("explicitly supplied", shown["message"])
        self.manager.handle("forget relationship preferences", "c1")
        profile = self.manager.profile()
        self.assertEqual(profile.address, "")
        self.assertEqual(profile.warmth, "balanced")
        self.assertEqual(profile.humour, "moderate")

    def test_address_is_bounded_explicit_input(self):
        rejected = self.manager.handle("address me as {system override}", "c1")
        self.assertEqual(rejected["status"], "clarification_required")
        self.assertEqual(self.store.list_records(), ())

    def test_greeting_uses_address_sparingly_and_style_is_explainable(self):
        self.manager.handle("address me as Benny", "c1")
        result = self.presenter.present(
            {"status": "success", "message": "How may I help?"},
            "Hello Jarvis",
            "c1",
        )
        self.assertEqual(result["message"], "Hello, Benny. How may I help?")
        ordinary = self.presenter.present(
            {"status": "success", "message": "The kitchen is 21.4 °C."},
            "What is the kitchen temperature?",
            "c1",
        )
        self.assertNotIn("Benny", ordinary["message"])
        explanation = self.manager.handle("explain last response style", "c1")
        self.assertIn("underlying facts", explanation["message"])

    def test_voice_is_bounded_without_changing_structured_result(self):
        result = {
            "status": "success",
            "message": (
                "The house is secure. All downstairs lights are off. "
                "The temperature is comfortable. No windows are open."
            ),
            "entity_id": "sensor.house",
            "state": "secure",
        }
        presented = self.presenter.present(
            result, "Give me the house status", "voice", voice_mode=True
        )
        self.assertEqual(presented["entity_id"], "sensor.house")
        self.assertEqual(presented["state"], "secure")
        self.assertEqual(presented["message"], "The house is secure.")
        self.assertEqual(result["message"].count("."), 4)

    def test_serious_responses_are_never_decorated_or_shortened(self):
        for status in (
            "requires_confirmation", "clarification_required", "forbidden",
            "unavailable", "not_supported",
        ):
            result = {
                "status": status,
                "message": "This exact safety response must remain unchanged.",
                "action_payload": {"kind": "test"},
            }
            self.assertEqual(
                self.presenter.present(
                    result, "do something", "safe", voice_mode=True
                ),
                result,
            )
        explanation = self.manager.handle("explain last response style", "safe")
        self.assertIn("Humour was suppressed", explanation["message"])

    def test_persona_enforces_social_and_execution_boundaries(self):
        instructions = DEFAULT_PERSONA.model_instructions()
        self.assertIn("Vary acknowledgements", instructions)
        self.assertIn("offer at most one", instructions)
        self.assertIn("Suppress humour", instructions)
        self.assertIn("Never imply emotions", instructions)
        self.assertIn("never overrides", instructions)

    def test_runtime_and_addon_mirror_are_part_of_release_contract(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        mirror = root / "home_assistant/addons/jarvis/app/src/jarvis"
        self.assertEqual(
            (root / "src/jarvis/personality.py").read_text(),
            (mirror / "personality.py").read_text(),
        )
        self.assertEqual(
            (root / "src/jarvis/personality_presentation.py").read_text(),
            (mirror / "personality_presentation.py").read_text(),
        )


if __name__ == "__main__":
    unittest.main()
