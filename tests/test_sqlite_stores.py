import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from jarvis.knowledge.store import KnowledgeNotFoundError
from jarvis.memory.store import MemoryNotFoundError
from jarvis.models.knowledge import KnowledgeRecord, KnowledgeSource, KnowledgeStatus, KnowledgeType
from jarvis.models.memory import MemoryConsentLevel, MemoryRecord, MemorySource, MemoryStatus, MemoryType
from jarvis.storage.sqlite_stores import SQLiteKnowledgeStore, SQLiteMemoryStore


class SQLiteStoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "jarvis.sqlite3"
        self.now = datetime.now(timezone.utc)

    def tearDown(self):
        self.directory.cleanup()

    def test_memory_survives_reopen_and_hard_delete_removes_it(self):
        record = MemoryRecord("memory-1", MemoryType.FACT, "Explicit fact", MemorySource.EXPLICIT_USER_REQUEST,
                              MemoryConsentLevel.EXPLICIT, self.now, self.now, tags=("home",), status=MemoryStatus.ACTIVE)
        store = SQLiteMemoryStore(self.path)
        store.create(record)
        store.close()
        reopened = SQLiteMemoryStore(self.path)
        self.assertEqual(reopened.get("memory-1").content, "Explicit fact")
        reopened.delete("memory-1")
        self.assertFalse(reopened.exists("memory-1"))
        with self.assertRaises(MemoryNotFoundError): reopened.get("memory-1")
        reopened.close()

    def test_knowledge_survives_reopen_and_replacement_does_not_duplicate(self):
        record = KnowledgeRecord("knowledge-1", KnowledgeType.HOME_REFERENCE, "Original", KnowledgeSource.USER_PROVIDED,
                                 self.now, self.now, title="Home", status=KnowledgeStatus.ACTIVE)
        store = SQLiteKnowledgeStore(self.path)
        store.create(record)
        store.close()
        reopened = SQLiteKnowledgeStore(self.path)
        replacement = KnowledgeRecord("knowledge-1", KnowledgeType.HOME_REFERENCE, "Replacement", KnowledgeSource.USER_PROVIDED,
                                      self.now, self.now, title="Home", status=KnowledgeStatus.ACTIVE)
        reopened.update(replacement)
        self.assertEqual([item.content for item in reopened.list_records()], ["Replacement"])
        reopened.delete("knowledge-1")
        with self.assertRaises(KnowledgeNotFoundError): reopened.get("knowledge-1")
        reopened.close()
