"""Policy-controlled writing of explicit durable memory."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Protocol

from jarvis.memory.policy import MemoryPolicy
from jarvis.memory.store import (
    DuplicateMemoryError,
    InvalidMemoryOperationError,
    MemoryNotFoundError,
    MemoryStore,
)
from jarvis.models.memory import (
    MemoryConsentLevel,
    MemoryRecord,
    MemoryRecordFactory,
)
from jarvis.models.memory_write import (
    ExplicitMemoryWriteRequest,
    MemoryCorrectionRequest,
    MemoryPolicyDecision,
    MemoryWriteResult,
    MemoryWriteStatus,
    UNSET,
)


class MemoryWriter(Protocol):
    """Writes approved explicit memories without retrieval behavior."""

    def create_explicit_memory(
        self,
        request: ExplicitMemoryWriteRequest,
    ) -> MemoryWriteResult:
        """Create one explicit memory after policy approval."""

    def correct_memory(
        self,
        request: MemoryCorrectionRequest,
    ) -> MemoryWriteResult:
        """Correct one existing memory after policy approval."""


class PolicyControlledMemoryWriter:
    """Construct and persist records only after a MemoryPolicy approval."""

    def __init__(
        self,
        store: MemoryStore,
        policy: MemoryPolicy,
        record_factory: MemoryRecordFactory,
        timestamp_factory: Callable[[], datetime],
    ) -> None:
        self._store = store
        self._policy = policy
        self._record_factory = record_factory
        self._timestamp_factory = timestamp_factory

    def create_explicit_memory(
        self,
        request: ExplicitMemoryWriteRequest,
    ) -> MemoryWriteResult:
        """Create an approved explicit record or return a policy outcome."""

        policy_result = self._policy.evaluate_creation(request)
        outcome = self._policy_outcome(policy_result.decision, policy_result.reason_code)
        if outcome is not None:
            return outcome

        record = self._record_factory.create(
            memory_type=request.memory_type,
            content=request.content,
            source=request.source,
            consent_level=self._record_consent_level(request.consent_level, request.is_sensitive),
            source_request_id=request.source_request_id,
            importance=request.importance,
            confidence=request.confidence,
            tags=request.tags,
            metadata=request.metadata,
        )

        try:
            stored_record = self._store.create(record)
        except DuplicateMemoryError:
            return MemoryWriteResult(MemoryWriteStatus.FAILED, "duplicate_memory")
        except InvalidMemoryOperationError:
            return MemoryWriteResult(MemoryWriteStatus.FAILED, "invalid_memory_request")

        return MemoryWriteResult(MemoryWriteStatus.CREATED, "created", stored_record)

    def correct_memory(self, request: MemoryCorrectionRequest) -> MemoryWriteResult:
        """Replace an approved memory while preserving identity and creation time."""

        try:
            existing_record = self._store.get(request.target_memory_id)
        except MemoryNotFoundError:
            return MemoryWriteResult(MemoryWriteStatus.FAILED, "memory_not_found")

        policy_result = self._policy.evaluate_correction(existing_record, request)
        outcome = self._policy_outcome(policy_result.decision, policy_result.reason_code)
        if outcome is not None:
            return outcome

        replacement = MemoryRecord(
            memory_id=existing_record.memory_id,
            memory_type=existing_record.memory_type,
            content=request.replacement_content,
            source=request.source,
            consent_level=self._record_consent_level(request.consent_level, request.is_sensitive),
            created_at=existing_record.created_at,
            updated_at=self._timestamp_factory(),
            source_request_id=request.source_request_id,
            expires_at=self._replacement_value(request.expires_at, existing_record.expires_at),
            importance=self._replacement_value(request.importance, existing_record.importance),
            confidence=self._replacement_value(request.confidence, existing_record.confidence),
            tags=self._replacement_value(request.tags, existing_record.tags),
            status=existing_record.status,
            metadata=self._replacement_value(request.metadata, existing_record.metadata),
        )

        try:
            stored_record = self._store.update(replacement)
        except InvalidMemoryOperationError:
            return MemoryWriteResult(MemoryWriteStatus.FAILED, "invalid_memory_request")

        return MemoryWriteResult(MemoryWriteStatus.UPDATED, "updated", stored_record)

    @staticmethod
    def _policy_outcome(
        decision: MemoryPolicyDecision,
        reason_code: str,
    ) -> MemoryWriteResult | None:
        if decision is MemoryPolicyDecision.REQUIRES_CONFIRMATION:
            return MemoryWriteResult(
                MemoryWriteStatus.REQUIRES_CONFIRMATION,
                reason_code,
                requires_confirmation=True,
            )
        if decision is MemoryPolicyDecision.REJECTED:
            return MemoryWriteResult(MemoryWriteStatus.REJECTED, reason_code)
        return None

    @staticmethod
    def _record_consent_level(
        requested_level: MemoryConsentLevel,
        is_sensitive: bool,
    ) -> MemoryConsentLevel:
        if is_sensitive:
            return MemoryConsentLevel.SENSITIVE_CONFIRMED
        return requested_level

    @staticmethod
    def _replacement_value(requested: object, current: object) -> object:
        return current if requested is UNSET else requested
