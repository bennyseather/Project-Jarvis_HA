"""Unit tests for the deterministic in-memory knowledge store."""

import unittest
from dataclasses import replace
from datetime import datetime, timezone

from jarvis.knowledge.in_memory_store import InMemoryKnowledgeStore
from jarvis.knowledge.store import DuplicateKnowledgeError, InvalidKnowledgeOperationError, KnowledgeNotFoundError
from jarvis.models.knowledge import KnowledgeRecord, KnowledgeRecordFactory, KnowledgeSource, KnowledgeStatus, KnowledgeType

TIME = datetime(2026, 7, 24, 12, 0, tzinfo=timezone.utc)


class InMemoryKnowledgeStoreTests(unittest.TestCase):
    def setUp(self) -> None: self.store = InMemoryKnowledgeStore()

    def test_create_get_and_ordered_list(self) -> None:
        self.store.create(self._record("knowledge-b", "Second"))
        self.store.create(self._record("knowledge-a", "First"))
        self.assertEqual(self.store.get("knowledge-a").content, "First")
        self.assertEqual([r.knowledge_id for r in self.store.list_records()], ["knowledge-a", "knowledge-b"])

    def test_duplicate_missing_update_delete_and_clear(self) -> None:
        self.store.create(self._record("knowledge-1", "First"))
        with self.assertRaises(DuplicateKnowledgeError): self.store.create(self._record("knowledge-1", "Again"))
        with self.assertRaises(KnowledgeNotFoundError): self.store.get("missing")
        with self.assertRaises(KnowledgeNotFoundError): self.store.update(self._record("missing", "Missing"))
        self.store.update(self._record("knowledge-1", "Replacement"))
        self.assertEqual(self.store.get("knowledge-1").content, "Replacement")
        self.store.delete("knowledge-1")
        self.assertFalse(self.store.exists("knowledge-1"))
        with self.assertRaises(KnowledgeNotFoundError): self.store.delete("knowledge-1")
        self.store.create(self._record("knowledge-2", "Second")); self.store.clear()
        self.assertEqual(self.store.list_records(), ())

    def test_defensive_copies_factory_and_validation(self) -> None:
        record = self._record("knowledge-1", "Original", {"nested": {"value": 1}})
        self.store.create(record); record.metadata["nested"]["value"] = 2
        returned = self.store.get("knowledge-1"); returned.metadata["nested"]["value"] = 3
        self.assertEqual(self.store.get("knowledge-1").metadata["nested"]["value"], 1)
        factory = KnowledgeRecordFactory(lambda: "fixed", lambda: TIME)
        self.assertEqual(factory.create(KnowledgeType.HOME_REFERENCE, "Content", KnowledgeSource.USER_PROVIDED).created_at, TIME)
        with self.assertRaises(InvalidKnowledgeOperationError): self.store.create(replace(record, knowledge_id=""))
        with self.assertRaises(InvalidKnowledgeOperationError): self.store.create("invalid")

    @staticmethod
    def _record(knowledge_id: str, content: str, metadata: dict[str, object] | None = None) -> KnowledgeRecord:
        return KnowledgeRecord(knowledge_id, KnowledgeType.HOME_REFERENCE, content,
            KnowledgeSource.USER_PROVIDED, TIME, TIME, status=KnowledgeStatus.ACTIVE,
            metadata={} if metadata is None else metadata)
