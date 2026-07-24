"""Unit tests for explicit, policy-controlled memory management."""

import unittest
from dataclasses import replace
from datetime import datetime, timezone

from jarvis.memory.in_memory_store import InMemoryMemoryStore
from jarvis.memory.manager import PolicyControlledMemoryManager
from jarvis.memory.policy import ExplicitMemoryPolicy
from jarvis.memory.store import MemoryNotFoundError
from jarvis.models.memory import (
    MemoryConsentLevel,
    MemoryRecord,
    MemorySource,
    MemoryStatus,
    MemoryType,
)
from jarvis.models.memory_management import (
    MemoryManagementAction,
    MemoryManagementQuery,
    MemoryManagementRequest,
    MemoryManagementStatus,
)


TIMESTAMP = datetime(2026, 7, 24, 12, 0, tzinfo=timezone.utc)


class FailingSecondDeleteStore(InMemoryMemoryStore):
    """Fail a multi-delete after one irreversible deletion."""

    def __init__(self) -> None:
        super().__init__()
        self._delete_calls = 0

    def delete(self, memory_id: str) -> None:
        self._delete_calls += 1
        if self._delete_calls == 2:
            raise MemoryNotFoundError("memory disappeared")
        super().delete(memory_id)


class MemoryManagerTests(unittest.TestCase):
    """Verify inspection, explicit confirmation, and hard-delete behavior."""

    def setUp(self) -> None:
        self.store = InMemoryMemoryStore()
        self.manager = PolicyControlledMemoryManager(self.store, ExplicitMemoryPolicy())

    def test_inspects_an_exact_authorized_memory_with_a_defensive_copy(self) -> None:
        self.store.create(
            self._record("memory-1", "Inspectable", metadata={"nested": {"value": 1}})
        )

        result = self.manager.manage(self._request(MemoryManagementAction.INSPECT, memory_id="memory-1"))

        self.assertEqual(result.status, MemoryManagementStatus.SUCCESS)
        result.record.metadata["nested"]["value"] = 2
        self.assertEqual(self.store.get("memory-1").metadata["nested"]["value"], 1)

    def test_finds_deterministic_non_content_candidates_with_exact_normalization(self) -> None:
        self.store.create(self._record("memory-b", "  Project   Jarvis ", tags=("Code",)))
        self.store.create(self._record("memory-a", "project jarvis", tags=("other",)))

        result = self.manager.manage(
            self._request(MemoryManagementAction.FIND, exact_content="PROJECT jarvis")
        )

        self.assertEqual(result.status, MemoryManagementStatus.SUCCESS)
        self.assertEqual([candidate.memory_id for candidate in result.candidates], ["memory-a", "memory-b"])
        self.assertFalse(hasattr(result.candidates[0], "content"))

    def test_match_deletion_requires_confirmation_and_hard_deletes_only_confirmed_scope(self) -> None:
        self.store.create(self._record("memory-a", "Project Jarvis", tags=("project",)))
        self.store.create(self._record("memory-b", "Project Jarvis", tags=("project",)))
        request = self._request(MemoryManagementAction.DELETE_MATCHES, tags=("PROJECT",))

        pending = self.manager.manage(request)
        confirmed = self.manager.manage(
            replace(request, has_confirmation=True, confirmation_token=pending.confirmation_token)
        )

        self.assertEqual(pending.status, MemoryManagementStatus.REQUIRES_CONFIRMATION)
        self.assertEqual([candidate.memory_id for candidate in pending.candidates], ["memory-a", "memory-b"])
        self.assertEqual(confirmed.status, MemoryManagementStatus.SUCCESS)
        self.assertEqual(confirmed.deleted_memory_ids, ("memory-a", "memory-b"))
        self.assertEqual(self.store.list_records(), ())

    def test_rejects_scope_changed_after_match_deletion_confirmation(self) -> None:
        self.store.create(self._record("memory-a", "Project Jarvis"))
        request = self._request(MemoryManagementAction.DELETE_MATCHES, exact_content="Project Jarvis")
        pending = self.manager.manage(request)
        self.store.create(self._record("memory-b", "Project Jarvis"))

        result = self.manager.manage(
            replace(request, has_confirmation=True, confirmation_token=pending.confirmation_token)
        )

        self.assertEqual(result.status, MemoryManagementStatus.REQUIRES_CONFIRMATION)
        self.assertEqual(result.reason_code, "matching_memory_scope_changed")
        self.assertEqual(len(self.store.list_records()), 2)

    def test_deletes_one_exact_identifier_without_second_confirmation(self) -> None:
        self.store.create(self._record("memory-1", "One"))

        result = self.manager.manage(self._request(MemoryManagementAction.DELETE_ONE, memory_id="memory-1"))

        self.assertEqual(result.status, MemoryManagementStatus.SUCCESS)
        self.assertEqual(result.deleted_count, 1)
        with self.assertRaises(MemoryNotFoundError):
            self.store.get("memory-1")

    def test_delete_all_requires_confirmation_and_does_not_include_sensitive_by_default(self) -> None:
        self.store.create(self._record("normal", "Normal"))
        self.store.create(
            self._record("sensitive", "Sensitive", consent_level=MemoryConsentLevel.SENSITIVE_CONFIRMED)
        )
        request = self._request(MemoryManagementAction.DELETE_ALL)
        pending = self.manager.manage(request)
        result = self.manager.manage(
            replace(request, has_confirmation=True, confirmation_token=pending.confirmation_token)
        )

        self.assertEqual(pending.status, MemoryManagementStatus.REQUIRES_CONFIRMATION)
        self.assertEqual(result.deleted_memory_ids, ("normal",))
        self.assertTrue(self.store.exists("sensitive"))

    def test_sensitive_management_needs_policy_confirmation_even_when_requested(self) -> None:
        self.store.create(
            self._record("sensitive", "Sensitive", consent_level=MemoryConsentLevel.SENSITIVE_CONFIRMED)
        )
        request = self._request(
            MemoryManagementAction.DELETE_ONE,
            memory_id="sensitive",
            include_sensitive=True,
        )

        rejected = self.manager.manage(request)
        approved = self.manager.manage(replace(request, has_confirmation=True))

        self.assertEqual(rejected.status, MemoryManagementStatus.REJECTED)
        self.assertEqual(approved.status, MemoryManagementStatus.SUCCESS)

    def test_sensitive_match_deletion_uses_confirmation_before_hard_delete(self) -> None:
        self.store.create(
            self._record(
                "sensitive",
                "Sensitive project",
                consent_level=MemoryConsentLevel.SENSITIVE_CONFIRMED,
            )
        )
        request = self._request(
            MemoryManagementAction.DELETE_MATCHES,
            exact_content="Sensitive project",
            include_sensitive=True,
        )

        pending = self.manager.manage(request)
        result = self.manager.manage(
            replace(request, has_confirmation=True, confirmation_token=pending.confirmation_token)
        )

        self.assertEqual(pending.status, MemoryManagementStatus.REQUIRES_CONFIRMATION)
        self.assertEqual(result.status, MemoryManagementStatus.SUCCESS)
        self.assertFalse(self.store.exists("sensitive"))

    def test_sensitive_delete_all_uses_confirmation_before_hard_delete(self) -> None:
        self.store.create(
            self._record(
                "sensitive",
                "Sensitive project",
                consent_level=MemoryConsentLevel.SENSITIVE_CONFIRMED,
            )
        )
        request = self._request(MemoryManagementAction.DELETE_ALL, include_sensitive=True)

        pending = self.manager.manage(request)
        result = self.manager.manage(
            replace(request, has_confirmation=True, confirmation_token=pending.confirmation_token)
        )

        self.assertEqual(pending.status, MemoryManagementStatus.REQUIRES_CONFIRMATION)
        self.assertEqual(result.status, MemoryManagementStatus.SUCCESS)
        self.assertFalse(self.store.exists("sensitive"))

    def test_rejects_unfiltered_match_deletion_and_reports_no_exact_match(self) -> None:
        self.store.create(self._record("memory-1", "One"))

        unfiltered = self.manager.manage(self._request(MemoryManagementAction.DELETE_MATCHES))
        missing = self.manager.manage(self._request(MemoryManagementAction.DELETE_ONE, memory_id="missing"))

        self.assertEqual(unfiltered.status, MemoryManagementStatus.REJECTED)
        self.assertEqual(missing.status, MemoryManagementStatus.NO_MATCH)

    def test_reports_partial_hard_deletion_without_rollback(self) -> None:
        store = FailingSecondDeleteStore()
        store.create(self._record("memory-a", "Same"))
        store.create(self._record("memory-b", "Same"))
        manager = PolicyControlledMemoryManager(store, ExplicitMemoryPolicy())
        request = self._request(MemoryManagementAction.DELETE_MATCHES, exact_content="Same")
        pending = manager.manage(request)

        result = manager.manage(
            replace(request, has_confirmation=True, confirmation_token=pending.confirmation_token)
        )

        self.assertEqual(result.status, MemoryManagementStatus.PARTIAL)
        self.assertEqual(result.deleted_memory_ids, ("memory-a",))
        self.assertFalse(store.exists("memory-a"))
        self.assertTrue(store.exists("memory-b"))

    def test_limits_listing_and_validates_query_limit(self) -> None:
        self.store.create(self._record("memory-a", "A"))
        self.store.create(self._record("memory-b", "B"))

        result = self.manager.manage(self._request(MemoryManagementAction.LIST, maximum_results=1))

        self.assertEqual([candidate.memory_id for candidate in result.candidates], ["memory-a"])
        with self.assertRaises(ValueError):
            MemoryManagementQuery(maximum_results=11)

    @staticmethod
    def _request(action: MemoryManagementAction, **kwargs: object) -> MemoryManagementRequest:
        query_fields = {
            name: kwargs.pop(name)
            for name in ("memory_id", "exact_content", "memory_types", "tags", "maximum_results", "include_sensitive")
            if name in kwargs
        }
        return MemoryManagementRequest(action, MemoryManagementQuery(**query_fields), **kwargs)

    @staticmethod
    def _record(
        memory_id: str,
        content: str,
        *,
        memory_type: MemoryType = MemoryType.FACT,
        consent_level: MemoryConsentLevel = MemoryConsentLevel.EXPLICIT,
        tags: tuple[str, ...] = (),
        metadata: dict[str, object] | None = None,
    ) -> MemoryRecord:
        return MemoryRecord(
            memory_id=memory_id,
            memory_type=memory_type,
            content=content,
            source=MemorySource.EXPLICIT_USER_REQUEST,
            consent_level=consent_level,
            created_at=TIMESTAMP,
            updated_at=TIMESTAMP,
            tags=tags,
            status=MemoryStatus.ACTIVE,
            metadata={} if metadata is None else metadata,
        )
