import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jarvis.management.natural_memory import NaturalMemoryController
from jarvis.memory.policy import ExplicitMemoryPolicy
from jarvis.memory.repeated_context import RepeatedContextExtractor, RepeatedContextLearner
from jarvis.memory.writer import PolicyControlledMemoryWriter
from jarvis.models.memory import MemoryRecordFactory, MemorySource
from jarvis.persona import DEFAULT_PERSONA
from jarvis.storage.conversation_store import SQLiteConversationStore
from jarvis.storage.sqlite_stores import SQLiteMemoryStore


class Clock:
    def __init__(self):
        self.value = datetime(2026, 7, 27, tzinfo=timezone.utc)

    def __call__(self):
        return self.value


class CandidateProvider:
    def __init__(self, *, sensitive=False):
        self.sensitive = sensitive

    def ask(self, request):
        return json.dumps({"candidate": {
            "key": "user.preferred_temperature",
            "content": "The user prefers 21 degrees indoors",
            "category": "preference",
            "sensitive": self.sensitive,
        }})


class M19ConversationMemoryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "jarvis.sqlite3"
        self.clock = Clock()

    def tearDown(self):
        self.directory.cleanup()

    def test_retention_uses_age_count_and_message_bounds_and_survives_reopen(self):
        store = SQLiteConversationStore(
            self.path, maximum_conversations=2, retention_days=3,
            maximum_messages=3, clock=self.clock,
        )
        for session in ("one", "two", "three"):
            store.add_message(session, "user", f"hello {session}")
            self.clock.value += timedelta(minutes=1)
        self.assertEqual(store.list_conversations(), ("three", "two"))
        for number in range(5):
            store.add_message("three", "user", f"message {number}")
        self.assertEqual([m.content for m in store.history("three", 3)],
                         ["message 2", "message 3", "message 4"])
        store.close()
        reopened = SQLiteConversationStore(
            self.path, maximum_conversations=2, retention_days=3,
            maximum_messages=3, clock=self.clock,
        )
        self.assertEqual(len(reopened.history("three", 3)), 3)
        self.clock.value += timedelta(days=4)
        reopened.prune()
        self.assertEqual(reopened.list_conversations(), ())
        reopened.close()

    def test_migration_preserves_pre_m19_memory_and_advances_schema(self):
        memory_store = SQLiteMemoryStore(self.path)
        memory_store.close()
        conversations = SQLiteConversationStore(self.path, clock=self.clock)
        conversations.close()
        connection = sqlite3.connect(self.path)
        self.assertEqual(connection.execute("SELECT version FROM schema_version").fetchone()[0], 4)
        self.assertIsNotNone(connection.execute(
            "SELECT name FROM sqlite_master WHERE name='memory_records'"
        ).fetchone())
        connection.close()

    def test_third_distinct_user_assertion_promotes_once_with_provenance(self):
        conversations = SQLiteConversationStore(self.path, clock=self.clock)
        memories = SQLiteMemoryStore(self.path)
        writer = PolicyControlledMemoryWriter(
            memories, ExplicitMemoryPolicy(),
            MemoryRecordFactory(timestamp_factory=self.clock), self.clock,
        )
        learner = RepeatedContextLearner(
            conversations, memories, writer,
            RepeatedContextExtractor(CandidateProvider()),
        )
        for index in range(3):
            message = conversations.add_message(
                "session", "user", f"I consistently prefer 21 degrees indoors {index}"
            )
            self.assertIsNone(learner.observe(message))
        records = memories.list_records()
        self.assertEqual(len(records), 1)
        self.assertIs(records[0].source, MemorySource.REPEATED_USER_CONTEXT)
        self.assertEqual(records[0].metadata["occurrence_threshold"], 3)
        extra = conversations.add_message("session", "user", "I still prefer 21 degrees indoors")
        learner.observe(extra)
        self.assertEqual(len(memories.list_records()), 1)
        conversations.close()
        memories.close()

    def test_sensitive_repetition_requires_confirmation(self):
        conversations = SQLiteConversationStore(self.path, clock=self.clock)
        memories = SQLiteMemoryStore(self.path)
        writer = PolicyControlledMemoryWriter(
            memories, ExplicitMemoryPolicy(),
            MemoryRecordFactory(timestamp_factory=self.clock), self.clock,
        )
        learner = RepeatedContextLearner(
            conversations, memories, writer,
            RepeatedContextExtractor(CandidateProvider(sensitive=True)),
        )
        pending = None
        for index in range(3):
            pending = learner.observe(conversations.add_message(
                "session", "user", f"My private stable detail is repeated {index}"
            ))
        self.assertEqual(pending["status"], "requires_confirmation")
        self.assertEqual(memories.list_records(), ())
        token = pending["confirmation_token"]
        self.assertEqual(learner.confirm(token)["status"], "success")
        self.assertEqual(len(memories.list_records()), 1)
        conversations.close()
        memories.close()

    def test_natural_controls_and_persona_safety_boundary(self):
        conversations = SQLiteConversationStore(self.path, clock=self.clock)
        memories = SQLiteMemoryStore(self.path)
        writer = PolicyControlledMemoryWriter(
            memories, ExplicitMemoryPolicy(),
            MemoryRecordFactory(timestamp_factory=self.clock), self.clock,
        )
        learner = RepeatedContextLearner(
            conversations, memories, writer,
            RepeatedContextExtractor(CandidateProvider()),
        )
        controller = NaturalMemoryController(memories, writer, conversations, learner)
        self.assertEqual(
            controller.handle("Remember that I prefer concise answers", "one")["status"],
            "success",
        )
        self.assertIn("concise answers", controller.handle(
            "What do you remember?", "one"
        )["message"])
        pending = controller.handle(
            "Remember that my medical diagnosis is private", "one"
        )
        self.assertEqual(pending["status"], "requires_confirmation")
        self.assertEqual(len(memories.list_records()), 1)
        confirmed = controller.handle(
            "confirm memory " + pending["confirmation_token"], "one"
        )
        self.assertEqual(confirmed["status"], "success")
        self.assertEqual(len(memories.list_records()), 2)
        self.assertIn("privacy", DEFAULT_PERSONA.model_instructions())
        self.assertIn("never invent", DEFAULT_PERSONA.model_instructions())
        conversations.close()
        memories.close()
