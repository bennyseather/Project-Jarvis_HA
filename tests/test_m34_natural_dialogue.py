import unittest

from jarvis.knowledge.in_memory_store import InMemoryKnowledgeStore
from jarvis.persona import DEFAULT_PERSONA
from jarvis.personality import PersonalityManager
from jarvis.personality_presentation import PersonalityPresenter
from jarvis.providers.assistant_proposal_provider import _INSTRUCTIONS


class M34NaturalDialogueTests(unittest.TestCase):
    def setUp(self):
        self.presenter = PersonalityPresenter(
            PersonalityManager(InMemoryKnowledgeStore())
        )

    def test_researched_voice_answer_drops_links_but_preserves_sources(self):
        result = {
            "status": "success",
            "researched": True,
            "message": (
                "The stable release is documented in the "
                "[release notes](https://example.com/releases).\n\n"
                "Sources:\n- Project — https://example.com/releases"
            ),
            "sources": ({"title": "Project", "url": "https://example.com/releases"},),
        }
        spoken = self.presenter.present(
            result, "What is the latest release?", "voice", voice_mode=True
        )
        self.assertNotIn("http", spoken["message"])
        self.assertIn("release notes", spoken["message"])
        self.assertEqual(spoken["sources"], result["sources"])

    def test_text_research_keeps_links(self):
        result = {
            "status": "success",
            "researched": True,
            "message": "Details: https://example.com/source",
            "sources": ({"title": "Source", "url": "https://example.com/source"},),
        }
        self.assertEqual(
            self.presenter.present(result, "Research this", "text"), result
        )

    def test_voice_removes_redundant_acknowledgement_when_answer_follows(self):
        result = {
            "status": "success",
            "message": "Certainly. The office temperature is 21.3 degrees.",
        }
        spoken = self.presenter.present(
            result, "What is the office temperature?", "voice", voice_mode=True
        )
        self.assertEqual(spoken["message"], "The office temperature is 21.3 degrees.")

    def test_dialogue_guidance_handles_followups_corrections_and_ambiguity(self):
        instructions = _INSTRUCTIONS + DEFAULT_PERSONA.model_instructions()
        self.assertIn("immediately preceding turn", instructions)
        self.assertIn("No, I meant the office", instructions)
        self.assertIn("ask one concise clarifying question", instructions)
        self.assertIn("never speak source URLs", instructions)

    def test_safety_results_are_not_rewritten(self):
        result = {
            "status": "requires_confirmation",
            "message": "Confirm this exact action before it is executed.",
            "sources": ({"title": "Policy", "url": "https://example.com"},),
        }
        self.assertEqual(
            self.presenter.present(result, "Do it", "safe", voice_mode=True),
            result,
        )


if __name__ == "__main__":
    unittest.main()
