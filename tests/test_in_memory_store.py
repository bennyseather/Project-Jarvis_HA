"""Unit tests for the deterministic in-memory memory store."""

import unittest
from datetime import datetime, timezone

from jarvis.memory.in_memory_store import InMemoryMemoryStore
from jarvis.memory.store import (
    DuplicateMemoryError,
    InvalidMemoryOperationError,
    MemoryNotFoundError,
)
from jarvis.models.memory import (
    MemoryConsentLevel,
    MemoryRecord,
    MemoryRecordFactory,
    MemorySource,
    MemoryStatus,
    MemoryType,
)


FIXED_TIME = datetime(2026, 7, 24, 12, 0, tzinfo=timezone.utc)


class InMemoryMemoryStoreTests(unittest.TestCase):
    """Verify persistence mechanics without policy or retrieval behavior."""

    def setUp(self) -> None:
        self.store = InMemoryMemoryStore()

    def test_creates_and_retrieves_a_memory(self) -> None:
        record = self._record("memory-1", "The guest room is upstairs.")

        created = self.store.create(record)
        retrieved = self.store.get("memory-1")

        self.assertEqual(created, record)
        self.assertEqual(retrieved, record)

    def test_lists_records_by_ascending_memory_identifier(self) -> None:
        self.store.create(self._record("memory-b", "Second"))
        self.store.create(self._record("memory-a", "First"))

        records = self.store.list_records()

        self.assertEqual([record.memory_id for record in records], ["memory-a", "memory-b"])

    def test_rejects_duplicate_identifiers(self) -> None:
        self.store.create(self._record("memory-1", "First"))

        with self.assertRaises(DuplicateMemoryError):
            self.store.create(self._record("memory-1", "Second"))

    def test_reports_existence(self) -> None:
        self.assertFalse(self.store.exists("memory-1"))
        self.store.create(self._record("memory-1", "Stored"))

        self.assertTrue(self.store.exists("memory-1"))

    def test_updates_without_retaining_old_content(self) -> None:
        self.store.create(self._record("memory-1", "Old content"))
        replacement = self._record("memory-1", "New content")

        updated = self.store.update(replacement)

        self.assertEqual(updated.content, "New content")
        self.assertEqual(self.store.get("memory-1").content, "New content")
        self.assertNotIn("Old content", [record.content for record in self.store.list_records()])

    def test_rejects_update_of_a_missing_record(self) -> None:
        with self.assertRaises(MemoryNotFoundError):
            self.store.update(self._record("missing", "Content"))

    def test_hard_deletes_a_record(self) -> None:
        self.store.create(self._record("memory-1", "Delete me"))

        self.store.delete("memory-1")

        self.assertFalse(self.store.exists("memory-1"))
        self.assertEqual(self.store.list_records(), ())
        with self.assertRaises(MemoryNotFoundError):
            self.store.get("memory-1")

    def test_rejects_deletion_of_a_missing_record(self) -> None:
        with self.assertRaises(MemoryNotFoundError):
            self.store.delete("missing")

    def test_clears_all_records(self) -> None:
        self.store.create(self._record("memory-1", "First"))
        self.store.create(self._record("memory-2", "Second"))

        self.store.clear()

        self.assertEqual(self.store.list_records(), ())
        self.assertFalse(self.store.exists("memory-1"))

    def test_prevents_mutation_of_internal_state(self) -> None:
        record = self._record("memory-1", "Original", metadata={"nested": {"value": 1}})
        self.store.create(record)
        record.metadata["nested"]["value"] = 2

        retrieved = self.store.get("memory-1")
        retrieved.metadata["nested"]["value"] = 3

        self.assertEqual(self.store.get("memory-1").metadata["nested"]["value"], 1)

    def test_factory_supports_deterministic_identifiers_and_timestamps(self) -> None:
        factory = MemoryRecordFactory(
            memory_id_factory=lambda: "memory-fixed",
            timestamp_factory=lambda: FIXED_TIME,
        )

        record = factory.create(
            MemoryType.PREFERENCE,
            "Use metric units.",
            MemorySource.EXPLICIT_USER_REQUEST,
            MemoryConsentLevel.EXPLICIT,
        )

        self.assertEqual(record.memory_id, "memory-fixed")
        self.assertEqual(record.created_at, FIXED_TIME)
        self.assertEqual(record.updated_at, FIXED_TIME)
        self.assertIsNone(record.expires_at)
        self.assertEqual(record.tags, ())

    def test_preserves_optional_record_fields(self) -> None:
        record = MemoryRecord(
            memory_id="memory-optional",
            memory_type=MemoryType.PROJECT,
            content="Project Jarvis uses Python.",
            source=MemorySource.EXPLICIT_USER_REQUEST,
            consent_level=MemoryConsentLevel.EXPLICIT,
            created_at=FIXED_TIME,
            updated_at=FIXED_TIME,
            source_request_id="request-1",
            expires_at=datetime(2027, 7, 24, tzinfo=timezone.utc),
            importance=0.8,
            confidence=0.9,
            tags=("jarvis", "project"),
            status=MemoryStatus.ACTIVE,
            metadata={"scope": "local"},
        )

        self.store.create(record)

        self.assertEqual(self.store.get("memory-optional"), record)

    def test_rejects_invalid_records(self) -> None:
        invalid = MemoryRecord(
            memory_id="",
            memory_type=MemoryType.FACT,
            content="Content",
            source=MemorySource.EXPLICIT_USER_REQUEST,
            consent_level=MemoryConsentLevel.EXPLICIT,
            created_at=FIXED_TIME,
            updated_at=FIXED_TIME,
        )

        with self.assertRaises(InvalidMemoryOperationError):
            self.store.create(invalid)

    @staticmethod
    def _record(
        memory_id: str,
        content: str,
        metadata: dict[str, object] | None = None,
    ) -> MemoryRecord:
        return MemoryRecord(
            memory_id=memory_id,
            memory_type=MemoryType.FACT,
            content=content,
            source=MemorySource.EXPLICIT_USER_REQUEST,
            consent_level=MemoryConsentLevel.EXPLICIT,
            created_at=FIXED_TIME,
            updated_at=FIXED_TIME,
            metadata={} if metadata is None else metadata,
        )
