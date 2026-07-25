"""Unit tests for policy-controlled explicit Knowledge writing."""

import unittest
from datetime import datetime, timezone

from jarvis.knowledge.in_memory_store import InMemoryKnowledgeStore
from jarvis.knowledge.policy import ExplicitKnowledgePolicy
from jarvis.knowledge.writer import PolicyControlledKnowledgeWriter
from jarvis.models.knowledge import KnowledgeRecordFactory, KnowledgeSource, KnowledgeType
from jarvis.models.knowledge_write import ExplicitKnowledgeWriteRequest, KnowledgeCorrectionRequest, KnowledgeWriteStatus, UNSET

CREATED = datetime(2026, 7, 24, 12, 0, tzinfo=timezone.utc)
UPDATED = datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc)


class KnowledgeWriterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = InMemoryKnowledgeStore()
        self.writer = PolicyControlledKnowledgeWriter(self.store, ExplicitKnowledgePolicy(),
            KnowledgeRecordFactory(lambda: "knowledge-1", lambda: CREATED), lambda: UPDATED)

    def test_creates_approved_knowledge_and_permits_duplicate_content(self) -> None:
        first = self.writer.create_explicit_knowledge(self._create())
        second_writer = PolicyControlledKnowledgeWriter(self.store, ExplicitKnowledgePolicy(),
            KnowledgeRecordFactory(lambda: "knowledge-2", lambda: CREATED), lambda: UPDATED)
        second = second_writer.create_explicit_knowledge(self._create())
        self.assertEqual(first.status, KnowledgeWriteStatus.CREATED)
        self.assertEqual(second.status, KnowledgeWriteStatus.CREATED)

    def test_rejects_unapproved_sensitive_and_unsupported_source_without_storing(self) -> None:
        for request in (self._create(is_explicitly_approved=False), self._create(is_sensitive=True),
                        self._create(source="invalid")):
            with self.subTest(request=request):
                self.assertEqual(self.writer.create_explicit_knowledge(request).status, KnowledgeWriteStatus.REJECTED)
        self.assertEqual(self.store.list_records(), ())

    def test_correction_preserves_identity_and_unset_semantics(self) -> None:
        original = self.writer.create_explicit_knowledge(self._create(title="Old", tags=("old",), metadata={"old": True})).record
        result = self.writer.correct_knowledge(KnowledgeCorrectionRequest(original.knowledge_id, "New content",
            KnowledgeSource.USER_PROVIDED, title=None, tags=(), metadata={}))
        self.assertEqual(result.status, KnowledgeWriteStatus.UPDATED)
        self.assertEqual(result.record.knowledge_id, original.knowledge_id)
        self.assertEqual(result.record.created_at, CREATED)
        self.assertEqual(result.record.updated_at, UPDATED)
        self.assertIsNone(result.record.title); self.assertEqual(result.record.tags, ()); self.assertEqual(result.record.metadata, {})
        self.assertIs(UNSET, KnowledgeCorrectionRequest("id", "x", KnowledgeSource.USER_PROVIDED).title)

    def test_reports_duplicate_invalid_and_missing_failures(self) -> None:
        self.writer.create_explicit_knowledge(self._create())
        self.assertEqual(self.writer.create_explicit_knowledge(self._create()).reason_code, "duplicate_knowledge")
        self.assertEqual(self.writer.create_explicit_knowledge(self._create(content=" ")).reason_code, "invalid_knowledge_request")
        self.assertEqual(self.writer.correct_knowledge(KnowledgeCorrectionRequest("missing", "x", KnowledgeSource.USER_PROVIDED)).reason_code, "knowledge_not_found")

    @staticmethod
    def _create(**kwargs: object) -> ExplicitKnowledgeWriteRequest:
        return ExplicitKnowledgeWriteRequest(kwargs.pop("content", "The boiler manual is in the utility room."),
            kwargs.pop("knowledge_type", KnowledgeType.DEVICE_DOCUMENTATION),
            kwargs.pop("source", KnowledgeSource.USER_PROVIDED), **kwargs)
