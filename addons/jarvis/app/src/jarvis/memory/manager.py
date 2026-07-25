"""Explicit, policy-controlled inspection and hard deletion of memory."""

from __future__ import annotations

from hashlib import sha256
from typing import Protocol

from jarvis.memory.policy import MemoryPolicy
from jarvis.memory.store import MemoryNotFoundError, MemoryStore
from jarvis.models.memory import MemoryRecord
from jarvis.models.memory_management import (
    MemoryManagementAction,
    MemoryManagementCandidate,
    MemoryManagementEligibility,
    MemoryManagementRequest,
    MemoryManagementResult,
    MemoryManagementStatus,
)


class MemoryManager(Protocol):
    """Manage explicitly requested durable memory without writing new content."""

    def manage(self, request: MemoryManagementRequest) -> MemoryManagementResult:
        """Inspect, find, or hard-delete policy-approved memory."""


class PolicyControlledMemoryManager:
    """Resolve explicit targets before requesting physical hard deletion."""

    def __init__(self, store: MemoryStore, policy: MemoryPolicy) -> None:
        self._store = store
        self._policy = policy

    def manage(self, request: MemoryManagementRequest) -> MemoryManagementResult:
        """Return a structured result without retaining deleted content."""

        if not request.is_explicit:
            return self._result(MemoryManagementStatus.REJECTED, "explicit_management_required")
        if request.action is MemoryManagementAction.INSPECT:
            return self._inspect(request)
        if request.action is MemoryManagementAction.LIST:
            return self._find(request, require_filter=False)
        if request.action is MemoryManagementAction.FIND:
            return self._find(request, require_filter=True)
        if request.action is MemoryManagementAction.DELETE_ONE:
            return self._delete_one(request)
        if request.action is MemoryManagementAction.DELETE_MATCHES:
            return self._delete_matches(request)
        if request.action is MemoryManagementAction.DELETE_ALL:
            return self._delete_all(request)
        return self._result(MemoryManagementStatus.REJECTED, "unsupported_management_action")

    def _inspect(self, request: MemoryManagementRequest) -> MemoryManagementResult:
        memory_id = request.query.memory_id
        if not memory_id:
            return self._result(MemoryManagementStatus.REJECTED, "memory_id_required")
        try:
            record = self._store.get(memory_id)
        except MemoryNotFoundError:
            return self._result(MemoryManagementStatus.NO_MATCH, "memory_not_found")
        if not self._is_eligible(record, request):
            return self._result(MemoryManagementStatus.REJECTED, "memory_not_authorized")
        return self._result(MemoryManagementStatus.SUCCESS, "inspected", record=record)

    def _find(
        self,
        request: MemoryManagementRequest,
        *,
        require_filter: bool,
    ) -> MemoryManagementResult:
        if require_filter and not self._has_filter(request):
            return self._result(MemoryManagementStatus.REJECTED, "management_filter_required")
        candidates = self._candidates(request)
        return self._result(
            MemoryManagementStatus.SUCCESS,
            "listed" if not require_filter else "found",
            candidates=candidates,
        )

    def _delete_one(self, request: MemoryManagementRequest) -> MemoryManagementResult:
        memory_id = request.query.memory_id
        if not memory_id:
            return self._result(MemoryManagementStatus.REJECTED, "memory_id_required")
        try:
            record = self._store.get(memory_id)
        except MemoryNotFoundError:
            return self._result(MemoryManagementStatus.NO_MATCH, "memory_not_found")
        if not self._is_eligible(record, request):
            return self._result(MemoryManagementStatus.REJECTED, "memory_not_authorized")
        return self._delete_records((record,))

    def _delete_matches(self, request: MemoryManagementRequest) -> MemoryManagementResult:
        if not self._has_filter(request):
            return self._result(MemoryManagementStatus.REJECTED, "management_filter_required")
        records = self._matching_records(request)
        if not records:
            return self._result(MemoryManagementStatus.NO_MATCH, "no_matching_memories")
        if not request.has_confirmation:
            return self._result(
                MemoryManagementStatus.REQUIRES_CONFIRMATION,
                "matching_memory_deletion_confirmation_required",
                candidates=self._to_candidates(records),
                requires_confirmation=True,
                confirmation_token=self._confirmation_token(records),
            )
        if request.confirmation_token != self._confirmation_token(records):
            return self._result(
                MemoryManagementStatus.REQUIRES_CONFIRMATION,
                "matching_memory_scope_changed",
                candidates=self._to_candidates(records),
                requires_confirmation=True,
                confirmation_token=self._confirmation_token(records),
            )
        return self._delete_records(records)

    def _delete_all(self, request: MemoryManagementRequest) -> MemoryManagementResult:
        records = self._eligible_records(request)
        if not records:
            return self._result(MemoryManagementStatus.NO_MATCH, "no_matching_memories")
        if not request.has_confirmation:
            return self._result(
                MemoryManagementStatus.REQUIRES_CONFIRMATION,
                "delete_all_confirmation_required",
                requires_confirmation=True,
                confirmation_token=self._confirmation_token(records),
            )
        if request.confirmation_token != self._confirmation_token(records):
            return self._result(
                MemoryManagementStatus.REQUIRES_CONFIRMATION,
                "delete_all_scope_changed",
                requires_confirmation=True,
                confirmation_token=self._confirmation_token(records),
            )
        return self._delete_records(records)

    def _delete_records(self, records: tuple[MemoryRecord, ...]) -> MemoryManagementResult:
        deleted_ids: list[str] = []
        for record in records:
            try:
                self._store.delete(record.memory_id)
            except MemoryNotFoundError:
                status = MemoryManagementStatus.PARTIAL if deleted_ids else MemoryManagementStatus.FAILED
                return self._result(status, "memory_deletion_failed", deleted_memory_ids=tuple(deleted_ids))
            deleted_ids.append(record.memory_id)
        return self._result(MemoryManagementStatus.SUCCESS, "deleted", deleted_memory_ids=tuple(deleted_ids))

    def _matching_records(self, request: MemoryManagementRequest) -> tuple[MemoryRecord, ...]:
        records = tuple(
            record
            for record in self._store.list_records()
            if self._is_eligible(record, request) and self._matches(record, request)
        )
        return records[: request.query.maximum_results]

    def _eligible_records(self, request: MemoryManagementRequest) -> tuple[MemoryRecord, ...]:
        return tuple(
            record
            for record in self._store.list_records()
            if self._is_eligible(record, request)
        )

    def _candidates(self, request: MemoryManagementRequest) -> tuple[MemoryManagementCandidate, ...]:
        return self._to_candidates(self._matching_records(request))

    @staticmethod
    def _to_candidates(records: tuple[MemoryRecord, ...]) -> tuple[MemoryManagementCandidate, ...]:
        return tuple(
            MemoryManagementCandidate(record.memory_id, record.memory_type, record.tags)
            for record in records
        )

    def _is_eligible(self, record: MemoryRecord, request: MemoryManagementRequest) -> bool:
        return (
            self._policy.evaluate_management(record, request).eligibility
            is MemoryManagementEligibility.ELIGIBLE
        )

    @staticmethod
    def _has_filter(request: MemoryManagementRequest) -> bool:
        query = request.query
        return bool(query.memory_id or query.exact_content or query.memory_types or query.tags)

    @staticmethod
    def _matches(record: MemoryRecord, request: MemoryManagementRequest) -> bool:
        query = request.query
        if query.memory_id and record.memory_id != query.memory_id:
            return False
        if query.exact_content and PolicyControlledMemoryManager._normalize(record.content) != PolicyControlledMemoryManager._normalize(query.exact_content):
            return False
        if query.memory_types and record.memory_type not in query.memory_types:
            return False
        requested_tags = {PolicyControlledMemoryManager._normalize(tag) for tag in query.tags}
        if requested_tags:
            record_tags = {PolicyControlledMemoryManager._normalize(tag) for tag in record.tags}
            if not requested_tags & record_tags:
                return False
        return True

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join(value.casefold().split())

    @staticmethod
    def _confirmation_token(records: tuple[MemoryRecord, ...]) -> str:
        identifiers = "\x1f".join(record.memory_id for record in records)
        return sha256(identifiers.encode()).hexdigest()

    @staticmethod
    def _result(
        status: MemoryManagementStatus,
        reason_code: str,
        *,
        candidates: tuple[MemoryManagementCandidate, ...] = (),
        deleted_memory_ids: tuple[str, ...] = (),
        requires_confirmation: bool = False,
        confirmation_token: str | None = None,
        record: MemoryRecord | None = None,
    ) -> MemoryManagementResult:
        return MemoryManagementResult(
            status=status,
            reason_code=reason_code,
            candidates=candidates,
            deleted_memory_ids=deleted_memory_ids,
            deleted_count=len(deleted_memory_ids),
            requires_confirmation=requires_confirmation,
            confirmation_token=confirmation_token,
            record=record,
        )
