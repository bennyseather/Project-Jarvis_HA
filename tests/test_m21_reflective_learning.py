import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from jarvis.management.natural_memory import NaturalMemoryController
from jarvis.memory.policy import ExplicitMemoryPolicy
from jarvis.memory.repeated_context import (
    RepeatedContextExtractor,
    RepeatedContextLearner,
)
from jarvis.memory.writer import PolicyControlledMemoryWriter
from jarvis.models.memory import (
    MemoryConsentLevel,
    MemoryRecordFactory,
    MemorySource,
    MemoryType,
)
from jarvis.reflection.manager import ReflectiveLearningManager
from jarvis.storage.conversation_store import SQLiteConversationStore
from jarvis.storage.reflection_store import SQLiteReflectionStore
from jarvis.storage.sqlite_stores import SQLiteMemoryStore


class _Clock:
    def __call__(self):
        return datetime(2026, 7, 28, tzinfo=timezone.utc)


class _CandidateProvider:
    def __init__(self, content="The user prefers 21 degrees in the office"):
        self.content = content

    def ask(self, _request):
        return json.dumps({"candidate": {
            "key": "user.office_temperature",
            "content": self.content,
            "category": "preference",
            "sensitive": False,
        }})


class M21ReflectiveLearningTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "jarvis.sqlite3"
        self.clock = _Clock()
        self.memories = SQLiteMemoryStore(self.path)
        self.conversations = SQLiteConversationStore(self.path, clock=self.clock)
        self.reflections = SQLiteReflectionStore(self.path)
        self.writer = PolicyControlledMemoryWriter(
            self.memories,
            ExplicitMemoryPolicy(),
            MemoryRecordFactory(timestamp_factory=self.clock),
            self.clock,
        )
        self.manager = ReflectiveLearningManager(
            self.memories, self.reflections, self.clock
        )

    def tearDown(self):
        self.reflections.close()
        self.conversations.close()
        self.memories.close()
        self.directory.cleanup()

    def test_schema_migration_and_reflections_survive_reopen(self):
        self._memory(
            "The user prefers concise office status answers",
            tags=("style_preference",),
        )
        self.manager.refresh()
        self.assertEqual(len(self.reflections.list_records()), 1)
        self.reflections.close()
        self.reflections = SQLiteReflectionStore(self.path)
        self.assertEqual(len(self.reflections.list_records()), 1)
        connection = sqlite3.connect(self.path)
        self.assertEqual(
            connection.execute(
                "SELECT version FROM schema_version"
            ).fetchone()[0],
            3,
        )
        connection.close()

    def test_bounded_context_links_memories_and_hard_delete_removes_links(self):
        first = self._memory("Benny uses the upstairs office")
        second = self._memory("The upstairs office contains Blocks")
        self.manager.refresh()
        context = self.manager.context_for("What is connected to the office?", 1)
        self.assertEqual(len(context), 1)
        self.assertEqual(context[0]["kind"], "relation")
        self.memories.delete(first.memory_id)
        self.manager.refresh()
        self.assertEqual(self.manager.records(), ())
        self.assertTrue(self.memories.exists(second.memory_id))

    def test_exact_duplicates_are_consolidated_without_history(self):
        first = self._memory(
            "Benny prefers concise answers",
            metadata={"source_conversation_ids": ["one"]},
        )
        second = self._memory(
            "Benny prefers concise answers",
            metadata={"source_conversation_ids": ["two"]},
        )
        self.manager.refresh()
        records = self.memories.list_records()
        self.assertEqual(len(records), 1)
        self.assertIn(
            records[0].memory_id,
            {first.memory_id, second.memory_id},
        )
        self.assertEqual(
            records[0].metadata["source_conversation_ids"], ["one", "two"]
        )

    def test_contradictions_uncertainty_and_sensitive_context_exclusion(self):
        self._memory(
            "The office preference is 21 degrees",
            metadata={"candidate_key": "office.temperature"},
        )
        self._memory(
            "The office preference is 20 degrees",
            metadata={"candidate_key": "office.temperature"},
        )
        self._memory(
            "A low confidence office observation",
            confidence=0.5,
        )
        self._memory(
            "The user's medical office detail",
            sensitive=True,
            tags=("style_preference",),
        )
        self.manager.refresh()
        kinds = {record.kind.value for record in self.manager.uncertainties()}
        self.assertEqual(kinds, {"contradiction", "uncertainty"})
        context_text = json.dumps(self.manager.context_for("office", 10))
        self.assertNotIn("medical", context_text)

    def test_promoted_conflict_requests_correction_and_opt_out_blocks_learning(self):
        provider = _CandidateProvider()
        learner = RepeatedContextLearner(
            self.conversations,
            self.memories,
            self.writer,
            RepeatedContextExtractor(provider),
            self.manager,
        )
        for index in range(3):
            learner.observe(self.conversations.add_message(
                "one", "user", f"I prefer 21 degrees in the office {index}"
            ))
        provider.content = "The user prefers 20 degrees in the office"
        conflict = learner.observe(self.conversations.add_message(
            "one", "user", "I now prefer 20 degrees in the office"
        ))
        self.assertEqual(conflict["status"], "clarification_required")
        self.assertIn("correct", conflict["message"])

        self.conversations.set_learning_disabled("two", True)
        before = len(self.memories.list_records())
        for index in range(3):
            learner.observe(self.conversations.add_message(
                "two", "user", f"I prefer 20 degrees in the office {index}"
            ))
        self.assertEqual(len(self.memories.list_records()), before)

    def test_natural_style_controls_provenance_and_connected_deletion(self):
        learner = RepeatedContextLearner(
            self.conversations,
            self.memories,
            self.writer,
            RepeatedContextExtractor(_CandidateProvider()),
            self.manager,
        )
        controller = NaturalMemoryController(
            self.memories,
            self.writer,
            self.conversations,
            learner,
            self.manager,
        )
        result = controller.handle("Keep your answers concise", "voice-one")
        self.assertEqual(result["status"], "success")
        self.assertTrue(any(
            record.kind.value == "style" for record in self.manager.records()
        ))
        learned = controller.handle("What have you learned about me?", "voice-one")
        self.assertIn("concise", learned["message"])
        provenance = controller.handle(
            "Why do you remember about concise?", "voice-one"
        )
        self.assertIn("explicitly asked", provenance["message"])

        self._memory("Benny uses the upstairs office")
        self._memory("The upstairs office contains Blocks")
        self.manager.refresh()
        deleted = controller.handle(
            "Forget everything connected to upstairs office", "voice-one"
        )
        self.assertEqual(deleted["status"], "success")
        self.assertNotIn("upstairs office", " ".join(
            record.content.casefold() for record in self.memories.list_records()
        ))

        controller.handle("Do not learn from this conversation", "voice-one")
        self.assertTrue(self.conversations.is_learning_disabled("voice-one"))

    def _memory(
        self,
        content,
        *,
        tags=(),
        metadata=None,
        confidence=1.0,
        sensitive=False,
    ):
        record = MemoryRecordFactory(
            timestamp_factory=self.clock
        ).create(
            MemoryType.PREFERENCE,
            content,
            MemorySource.EXPLICIT_USER_REQUEST,
            MemoryConsentLevel.SENSITIVE_CONFIRMED
            if sensitive else MemoryConsentLevel.EXPLICIT,
            tags=tags,
            metadata={} if metadata is None else metadata,
            confidence=confidence,
        )
        return self.memories.create(record)


if __name__ == "__main__":
    unittest.main()
