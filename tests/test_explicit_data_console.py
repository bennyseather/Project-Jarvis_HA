import unittest
from datetime import datetime, timezone

from jarvis.knowledge.in_memory_store import InMemoryKnowledgeStore
from jarvis.knowledge.policy import ExplicitKnowledgePolicy
from jarvis.knowledge.writer import PolicyControlledKnowledgeWriter
from jarvis.management.console_commands import ExplicitDataConsole
from jarvis.memory.in_memory_store import InMemoryMemoryStore
from jarvis.memory.manager import PolicyControlledMemoryManager
from jarvis.memory.policy import ExplicitMemoryPolicy
from jarvis.memory.writer import PolicyControlledMemoryWriter
from jarvis.models.knowledge import KnowledgeRecordFactory
from jarvis.models.memory import MemoryRecordFactory


class ExplicitDataConsoleTests(unittest.TestCase):
    def setUp(self):
        clock = lambda: datetime.now(timezone.utc)
        self.memories = InMemoryMemoryStore()
        self.knowledge = InMemoryKnowledgeStore()
        self.console = ExplicitDataConsole(
            PolicyControlledMemoryWriter(self.memories, ExplicitMemoryPolicy(), MemoryRecordFactory(memory_id_factory=lambda:"memory-1", timestamp_factory=clock), clock),
            PolicyControlledMemoryManager(self.memories, ExplicitMemoryPolicy()),
            PolicyControlledKnowledgeWriter(self.knowledge, ExplicitKnowledgePolicy(), KnowledgeRecordFactory(knowledge_id_factory=lambda:"knowledge-1", timestamp_factory=clock), clock),
            self.knowledge,
        )

    def test_explicit_memory_lifecycle(self):
        created = self.console.handle("memory remember The hall light is a safe test.")
        self.assertEqual(created["status"], "created")
        self.assertEqual(self.console.handle("memory list")["items"][0]["id"], "memory-1")
        self.assertEqual(self.console.handle("memory correct memory-1 | The hall light is off.")["status"], "updated")
        self.assertEqual(self.console.handle("memory forget memory-1")["deleted"], 1)

    def test_sensitive_memory_requires_separate_confirmation(self):
        pending = self.console.handle("memory remember-sensitive private detail")
        self.assertEqual(pending["status"], "requires_confirmation")
        self.assertFalse(self.memories.exists("memory-1"))
        self.assertEqual(self.console.handle(f"memory confirm {pending['token']}")["status"], "created")
        deletion = self.console.handle("memory forget-sensitive memory-1")
        self.assertEqual(self.console.handle(f"memory confirm-delete {deletion['token']}")["deleted"], 1)

    def test_knowledge_lifecycle_and_model_commands_are_not_claimed(self):
        self.assertIsNone(self.console.handle("normal assistant request"))
        self.assertEqual(self.console.handle("knowledge add Blocks is the safe test light.")["status"], "created")
        self.assertEqual(self.console.handle("knowledge correct knowledge-1 | Blocks is currently safe.")["status"], "updated")
        self.assertEqual(self.console.handle("knowledge forget knowledge-1")["status"], "success")
