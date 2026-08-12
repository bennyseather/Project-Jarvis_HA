import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jarvis.episodic_memory import EpisodicMemoryManager, EpisodicPolicy
from jarvis.knowledge.in_memory_store import InMemoryKnowledgeStore
from jarvis.management.natural_memory import NaturalMemoryController
from jarvis.memory.in_memory_store import InMemoryMemoryStore
from jarvis.memory.policy import ExplicitMemoryPolicy
from jarvis.models.memory import MemoryConsentLevel, MemoryType
from jarvis.models.memory_retrieval import MemoryRetrievalQuery
from jarvis.storage.conversation_store import SQLiteConversationStore


class FakeReasoning:
    def __init__(self):
        self.calls = []

    def reason(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "status": "success",
            "message": "We selected the local-first research design and left voice activation for a later milestone.",
        }


class FakeLearner:
    def confirm(self, token):
        return {"status": "forbidden", "message": "invalid"}

    def cancel(self, token):
        pass


class M30EpisodicContinuityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.now = datetime(2026, 8, 1, 12, tzinfo=timezone.utc)
        self.clock = lambda: self.now
        self.conversations = SQLiteConversationStore(
            Path(self.temp.name) / "episodes.sqlite3",
            clock=self.clock,
            maximum_messages=100,
        )
        self.memories = InMemoryMemoryStore()
        self.reasoning = FakeReasoning()
        self.manager = EpisodicMemoryManager(
            self.memories,
            self.conversations,
            EpisodicPolicy(),
            reasoning=self.reasoning,
            clock=self.clock,
        )

    def tearDown(self):
        self.conversations.close()
        self.temp.cleanup()

    def _conversation(self, identifier="c1", *, sensitive=False):
        messages = [
            "Let us discuss the local research design",
            "I agree that SearXNG should remain local",
            "We should review voice activation later",
        ]
        if sensitive:
            messages[1] = "My medical diagnosis should be considered"
        for text in messages:
            self.conversations.add_message(identifier, "user", text)
            self.conversations.add_message(identifier, "assistant", "Acknowledged.")

    def test_policy_is_bounded_and_validated(self):
        policy = EpisodicPolicy.from_config({})
        self.assertEqual(policy.retention_days, 30)
        self.assertEqual(policy.maximum_episodes, 50)
        with self.assertRaises(ValueError):
            EpisodicPolicy.from_config({"retention_days": 0})

    def test_explicit_summary_uses_reasoning_without_storing_transcript(self):
        self._conversation()
        result = self.manager.handle("remember this conversation", "c1")
        self.assertEqual(result["status"], "success")
        record = self.memories.list_records()[0]
        self.assertEqual(record.memory_type, MemoryType.CONVERSATION_SUMMARY)
        self.assertEqual(record.consent_level, MemoryConsentLevel.EXPLICIT)
        self.assertNotIn("Let us discuss", record.content)
        self.assertEqual(record.metadata["message_count"], 6)
        self.assertNotIn("transcript", record.metadata)
        self.assertEqual(len(self.reasoning.calls), 1)

    def test_sensitive_summary_requires_confirmation(self):
        self._conversation(sensitive=True)
        pending = self.manager.handle("remember this conversation", "c1")
        self.assertEqual(pending["status"], "requires_confirmation")
        self.assertEqual(self.memories.list_records(), ())
        result = self.manager.confirm(pending["confirmation_token"])
        self.assertEqual(result["status"], "success")
        self.assertEqual(
            self.memories.list_records()[0].consent_level,
            MemoryConsentLevel.SENSITIVE_CONFIRMED,
        )
        self.assertEqual(
            self.manager._redact_credentials("The password is hunter2."),
            "The password [redacted]",
        )

    def test_automatic_summary_is_local_low_sensitivity_and_expires(self):
        self._conversation()
        self.manager.observe("c1")
        record = self.memories.list_records()[0]
        self.assertEqual(record.consent_level, MemoryConsentLevel.AUTOMATIC_LOW_SENSITIVITY)
        self.assertEqual(len(self.reasoning.calls), 0)
        self.assertIsNotNone(record.expires_at)
        self.now += timedelta(days=31)
        self.manager.prune()
        self.assertEqual(self.memories.list_records(), ())

    def test_retrieval_policy_allows_nonsensitive_episodes_only(self):
        self._conversation()
        self.manager.observe("c1")
        record = self.memories.list_records()[0]
        decision = ExplicitMemoryPolicy().evaluate_retrieval(
            record,
            MemoryRetrievalQuery(query_text="research", evaluation_time=self.now),
        )
        self.assertEqual(decision.reason_code, "eligible")

    def test_inspect_topic_delete_and_clear_commands(self):
        self._conversation()
        self.manager.handle("remember this conversation", "c1")
        self.assertIn("local-first", self.manager.handle("what were we discussing?", "c1")["message"])
        self.assertIn("local-first", self.manager.handle("what did we decide about research?", "c1")["message"])
        self.assertIn("Recent conversation summaries", self.manager.handle("show recent conversations", "c1")["message"])
        deleted = self.manager.handle("forget conversations about research", "c1")
        self.assertIn("1 matching", deleted["message"])
        self.assertEqual(self.memories.list_records(), ())
        self.assertTrue(self.conversations.list_conversations())
        cleared = self.manager.handle("clear conversation history", "c1")
        self.assertIn("recent conversation", cleared["message"])
        self.assertEqual(self.conversations.list_conversations(), ())

    def test_episode_commands_are_excluded_from_automatic_recreation(self):
        self._conversation()
        self.manager.observe("c1")
        self.assertTrue(self.manager.is_command("forget this conversation"))
        self.manager.handle("forget this conversation", "c1")
        self.assertEqual(self.memories.list_records(), ())

    def test_pinned_records_do_not_expire_and_capacity_remains_bounded(self):
        policy = EpisodicPolicy(maximum_episodes=1)
        manager = EpisodicMemoryManager(
            self.memories, self.conversations, policy,
            reasoning=self.reasoning, clock=self.clock,
        )
        self._conversation("c1")
        self.assertEqual(manager.handle("pin this conversation", "c1")["status"], "success")
        self._conversation("c2")
        blocked = manager.handle("pin this conversation", "c2")
        self.assertEqual(blocked["status"], "clarification_required")
        self.now += timedelta(days=365)
        manager.prune()
        self.assertEqual(len(self.memories.list_records()), 1)

    def test_natural_controller_delegates_sensitive_confirmation(self):
        self._conversation(sensitive=True)
        controller = NaturalMemoryController(
            self.memories, None, self.conversations, FakeLearner(),
            episodic_manager=self.manager,
        )
        pending = controller.handle("remember this conversation", "c1")
        confirmed = controller.handle(
            f"confirm memory {pending['confirmation_token']}", "c1"
        )
        self.assertEqual(confirmed["status"], "success")

    def test_release_mirror_and_future_voice_activation_note(self):
        root = Path(__file__).resolve().parents[1]
        mirror = root / "home_assistant/addons/jarvis/app/src/jarvis/episodic_memory.py"
        self.assertTrue(mirror.exists())
        self.assertEqual((root / "src/jarvis/episodic_memory.py").read_text(), mirror.read_text())
        roadmap = (root / "docs/roadmap.md").read_text()
        self.assertIn("voice activation", roadmap.casefold())
        config = (root / "home_assistant/addons/jarvis/config.yaml").read_text()
        self.assertIn('version: "0.34.4"', config)
        self.assertIn("episodic_retention_days", config)


if __name__ == "__main__":
    unittest.main()
