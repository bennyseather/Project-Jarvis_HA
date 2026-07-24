"""Unit tests for policy-controlled explicit memory writing."""

import unittest
from dataclasses import replace
from datetime import datetime, timezone

from jarvis.memory.in_memory_store import InMemoryMemoryStore
from jarvis.memory.policy import ExplicitMemoryPolicy
from jarvis.memory.writer import PolicyControlledMemoryWriter
from jarvis.models.memory import (
    MemoryConsentLevel,
    MemoryRecordFactory,
    MemorySource,
    MemoryType,
)
from jarvis.models.memory_write import (
    ExplicitMemoryWriteRequest,
    MemoryCorrectionRequest,
    MemoryWriteStatus,
    UNSET,
)


CREATED_AT = datetime(2026, 7, 24, 12, 0, tzinfo=timezone.utc)
UPDATED_AT = datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc)


class MemoryWriterTests(unittest.TestCase):
    """Verify explicit, policy-approved create and correction behavior."""

    def setUp(self) -> None:
        self.store = InMemoryMemoryStore()
        self.writer = PolicyControlledMemoryWriter(
            store=self.store,
            policy=ExplicitMemoryPolicy(),
            record_factory=MemoryRecordFactory(
                memory_id_factory=lambda: "memory-1",
                timestamp_factory=lambda: CREATED_AT,
            ),
            timestamp_factory=lambda: UPDATED_AT,
        )

    def test_creates_each_initially_eligible_explicit_memory_type(self) -> None:
        for memory_type in (
            MemoryType.PREFERENCE,
            MemoryType.FACT,
            MemoryType.INSTRUCTION,
            MemoryType.PROJECT,
        ):
            with self.subTest(memory_type=memory_type):
                writer = self._writer_with_id(memory_type.value)

                result = writer.create_explicit_memory(self._create_request(memory_type))

                self.assertEqual(result.status, MemoryWriteStatus.CREATED)
                self.assertEqual(result.record.memory_type, memory_type)

    def test_rejects_missing_explicit_consent_without_storing(self) -> None:
        result = self.writer.create_explicit_memory(
            self._create_request(MemoryType.FACT, is_explicit=False)
        )

        self.assertEqual(result.status, MemoryWriteStatus.REJECTED)
        self.assertEqual(result.reason_code, "explicit_consent_required")
        self.assertEqual(self.store.list_records(), ())

    def test_rejects_inferred_or_implicit_source_without_storing(self) -> None:
        result = self.writer.create_explicit_memory(
            self._create_request(
                MemoryType.PREFERENCE,
                source=MemorySource.LEARNED_PREFERENCE,
            )
        )

        self.assertEqual(result.status, MemoryWriteStatus.REJECTED)
        self.assertEqual(result.reason_code, "invalid_creation_source")
        self.assertEqual(self.store.list_records(), ())

    def test_rejects_reserved_memory_types_without_storing(self) -> None:
        for memory_type in (MemoryType.EPISODIC, MemoryType.CONVERSATION_SUMMARY):
            with self.subTest(memory_type=memory_type):
                result = self.writer.create_explicit_memory(self._create_request(memory_type))

                self.assertEqual(result.status, MemoryWriteStatus.REJECTED)
                self.assertEqual(result.reason_code, "reserved_memory_type")
                self.assertEqual(self.store.list_records(), ())

    def test_requires_confirmation_for_sensitive_memory_without_storing(self) -> None:
        result = self.writer.create_explicit_memory(
            self._create_request(MemoryType.FACT, is_sensitive=True)
        )

        self.assertEqual(result.status, MemoryWriteStatus.REQUIRES_CONFIRMATION)
        self.assertTrue(result.requires_confirmation)
        self.assertEqual(self.store.list_records(), ())

    def test_preserves_provenance_optional_fields_and_deterministic_factories(self) -> None:
        result = self.writer.create_explicit_memory(
            self._create_request(
                MemoryType.PROJECT,
                source_request_id="request-1",
                tags=("jarvis",),
                importance=0.8,
                confidence=0.9,
                metadata={"scope": "local"},
            )
        )

        self.assertEqual(result.record.memory_id, "memory-1")
        self.assertEqual(result.record.created_at, CREATED_AT)
        self.assertEqual(result.record.updated_at, CREATED_AT)
        self.assertEqual(result.record.source_request_id, "request-1")
        self.assertEqual(result.record.tags, ("jarvis",))
        self.assertEqual(result.record.metadata, {"scope": "local"})

    def test_returns_failed_for_duplicate_store_identifiers(self) -> None:
        self._create_memory()

        result = self.writer.create_explicit_memory(self._create_request(MemoryType.FACT))

        self.assertEqual(result.status, MemoryWriteStatus.FAILED)
        self.assertEqual(result.reason_code, "duplicate_memory")

    def test_returns_failed_for_an_invalid_memory_request(self) -> None:
        result = self.writer.create_explicit_memory(
            self._create_request(MemoryType.FACT, content=" ")
        )

        self.assertEqual(result.status, MemoryWriteStatus.FAILED)
        self.assertEqual(result.reason_code, "invalid_memory_request")

    def test_corrects_memory_and_replaces_prior_content(self) -> None:
        original = self._create_memory()

        result = self.writer.correct_memory(
            MemoryCorrectionRequest(
                target_memory_id=original.memory_id,
                replacement_content="The guest room is on the first floor.",
                source=MemorySource.USER_CORRECTION,
                consent_level=MemoryConsentLevel.EXPLICIT,
                source_request_id="request-correction",
            )
        )

        self.assertEqual(result.status, MemoryWriteStatus.UPDATED)
        self.assertEqual(result.record.memory_id, original.memory_id)
        self.assertEqual(result.record.created_at, CREATED_AT)
        self.assertEqual(result.record.updated_at, UPDATED_AT)
        self.assertEqual(result.record.content, "The guest room is on the first floor.")
        self.assertNotIn(
            "The guest room is upstairs.",
            [record.content for record in self.store.list_records()],
        )

    def test_correction_preserves_omitted_optional_fields_with_unset(self) -> None:
        original = self._create_memory(
            tags=("home",),
            importance=0.6,
            confidence=0.7,
            metadata={"room": "guest"},
        )

        result = self.writer.correct_memory(self._correction(original.memory_id))

        self.assertEqual(result.record.tags, ("home",))
        self.assertEqual(result.record.importance, 0.6)
        self.assertEqual(result.record.confidence, 0.7)
        self.assertEqual(result.record.metadata, {"room": "guest"})
        self.assertIs(UNSET, self._correction(original.memory_id).tags)

    def test_correction_replaces_provided_optional_values(self) -> None:
        original = self._create_memory(tags=("old",), importance=0.1, metadata={"old": True})

        result = self.writer.correct_memory(
            self._correction(
                original.memory_id,
                tags=("new",),
                importance=0.9,
                metadata={"new": True},
            )
        )

        self.assertEqual(result.record.tags, ("new",))
        self.assertEqual(result.record.importance, 0.9)
        self.assertEqual(result.record.metadata, {"new": True})

    def test_correction_clears_nullable_values_with_none(self) -> None:
        original = self._create_memory()
        original = replace(
            original,
            expires_at=datetime(2027, 7, 24, tzinfo=timezone.utc),
            importance=0.5,
            confidence=0.6,
        )
        self.store.update(original)

        result = self.writer.correct_memory(
            self._correction(
                original.memory_id,
                expires_at=None,
                importance=None,
                confidence=None,
            )
        )

        self.assertIsNone(result.record.expires_at)
        self.assertIsNone(result.record.importance)
        self.assertIsNone(result.record.confidence)

    def test_correction_replaces_collections_with_empty_values(self) -> None:
        original = self._create_memory(tags=("home",), metadata={"room": "guest"})

        result = self.writer.correct_memory(
            self._correction(original.memory_id, tags=(), metadata={})
        )

        self.assertEqual(result.record.tags, ())
        self.assertEqual(result.record.metadata, {})

    def test_returns_failed_for_a_missing_correction_target(self) -> None:
        result = self.writer.correct_memory(self._correction("missing"))

        self.assertEqual(result.status, MemoryWriteStatus.FAILED)
        self.assertEqual(result.reason_code, "memory_not_found")

    def test_rejected_correction_does_not_modify_the_store(self) -> None:
        original = self._create_memory()

        result = self.writer.correct_memory(self._correction(original.memory_id, is_explicit=False))

        self.assertEqual(result.status, MemoryWriteStatus.REJECTED)
        self.assertEqual(self.store.get(original.memory_id), original)

    def test_sensitive_correction_requires_confirmation_without_update(self) -> None:
        original = self._create_memory()

        result = self.writer.correct_memory(
            self._correction(original.memory_id, is_sensitive=True)
        )

        self.assertEqual(result.status, MemoryWriteStatus.REQUIRES_CONFIRMATION)
        self.assertEqual(self.store.get(original.memory_id), original)

    def _create_memory(self, **kwargs: object):
        result = self.writer.create_explicit_memory(self._create_request(MemoryType.FACT, **kwargs))
        return result.record

    @staticmethod
    def _create_request(memory_type: MemoryType, **kwargs: object) -> ExplicitMemoryWriteRequest:
        return ExplicitMemoryWriteRequest(
            content=kwargs.pop("content", "The guest room is upstairs."),
            memory_type=memory_type,
            source=kwargs.pop("source", MemorySource.EXPLICIT_USER_REQUEST),
            consent_level=kwargs.pop("consent_level", MemoryConsentLevel.EXPLICIT),
            **kwargs,
        )

    @staticmethod
    def _correction(memory_id: str, **kwargs: object) -> MemoryCorrectionRequest:
        return MemoryCorrectionRequest(
            target_memory_id=memory_id,
            replacement_content="The guest room is on the first floor.",
            source=MemorySource.USER_CORRECTION,
            consent_level=MemoryConsentLevel.EXPLICIT,
            **kwargs,
        )

    @staticmethod
    def _writer_with_id(memory_id: str) -> PolicyControlledMemoryWriter:
        return PolicyControlledMemoryWriter(
            store=InMemoryMemoryStore(),
            policy=ExplicitMemoryPolicy(),
            record_factory=MemoryRecordFactory(
                memory_id_factory=lambda: memory_id,
                timestamp_factory=lambda: CREATED_AT,
            ),
            timestamp_factory=lambda: UPDATED_AT,
        )
