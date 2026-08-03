import unittest
from pathlib import Path

from jarvis.knowledge.in_memory_store import InMemoryKnowledgeStore
from jarvis.persona import DEFAULT_PERSONA
from jarvis.personality import PersonalityManager, PersonalityProfile
from jarvis.personality_presentation import PersonalityPresenter


class M36ContextualPersonalityTests(unittest.TestCase):
    def setUp(self):
        defaults = PersonalityProfile(
            address="Benny", humour="subtle", warmth="balanced",
            formality="refined", verbosity="concise", proactivity="balanced",
        )
        self.manager = PersonalityManager(
            InMemoryKnowledgeStore(), default_profile=defaults
        )
        self.presenter = PersonalityPresenter(self.manager)

    def test_complete_profile_includes_proactivity_and_configured_address(self):
        self.assertEqual(self.manager.profile().address, "Benny")
        self.assertEqual(self.manager.profile().proactivity, "balanced")
        result = self.manager.handle("set personality proactivity proactive")
        self.assertEqual(result["status"], "success")
        self.assertEqual(self.manager.profile().proactivity, "proactive")
        self.assertIn("proactivity proactive", self.manager.handle("show personality")["message"])

    def test_diagnostics_explain_mode_and_influence_without_mutating_result(self):
        result = {"status": "success", "message": "The kitchen light is off.", "state": "off"}
        presented = self.presenter.present(result, "Is the kitchen light on?", "c1")
        self.assertEqual(presented, result)
        diagnostic = self.manager.handle("show personality diagnostics", "c1")
        self.assertIn("home interaction", diagnostic["message"])
        self.assertIn("facts, permissions and actions were unchanged", diagnostic["message"])

    def test_protected_results_remain_exact_and_are_diagnosable(self):
        result = {"status": "requires_confirmation", "message": "Confirm the lock action.", "payload": {"lock": True}}
        self.assertEqual(
            self.presenter.present(result, "Lock the door", "safe", voice_mode=True),
            result,
        )
        diagnostic = self.manager.handle("personality diagnostics", "safe")
        self.assertIn("protected exact response", diagnostic["message"])

    def test_identity_guidance_is_local_first_and_privacy_bounded(self):
        instructions = DEFAULT_PERSONA.model_instructions()
        context = self.manager.profile().context()["presentation"]
        self.assertIn("explicit local context first", instructions)
        self.assertIn("never merge people", instructions)
        self.assertIn("explicit local memory", context)
        self.assertIn("sufficiently disambiguated", context)

    def test_home_assistant_options_and_runtime_mirror_are_complete(self):
        root = Path(__file__).resolve().parents[1]
        config = (root / "home_assistant/addons/jarvis/config.yaml").read_text()
        entrypoint = (root / "home_assistant/addons/jarvis/addon_entrypoint.py").read_text()
        for setting in ("humour", "warmth", "formality", "verbosity", "proactivity"):
            self.assertIn(f"personality_{setting}", config)
            self.assertIn(f'personality_{setting}', entrypoint)
        self.assertEqual(
            (root / "src/jarvis/personality.py").read_text(),
            (root / "home_assistant/addons/jarvis/app/src/jarvis/personality.py").read_text(),
        )

    def test_validated_defaults_survive_configuration_and_service_lifecycle(self):
        root = Path(__file__).resolve().parents[1]
        application = (root / "src/jarvis/core/application.py").read_text()
        container = (root / "src/jarvis/core/container.py").read_text()
        self.assertIn("self.container.default_personality = default_personality", application)
        self.assertIn("default_profile=self.container.default_personality", application)
        self.assertIn("self.default_personality = None", container)
        self.assertNotIn("default_profile=default_personality,", application)


if __name__ == "__main__":
    unittest.main()
