"""Policy-controlled writing of explicitly approved Knowledge."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Protocol

from jarvis.knowledge.policy import KnowledgePolicy
from jarvis.knowledge.store import DuplicateKnowledgeError, InvalidKnowledgeOperationError, KnowledgeNotFoundError, KnowledgeStore
from jarvis.models.knowledge import KnowledgeRecord, KnowledgeRecordFactory
from jarvis.models.knowledge_write import (
    ExplicitKnowledgeWriteRequest, KnowledgeCorrectionRequest, KnowledgePolicyDecision,
    KnowledgeWriteResult, KnowledgeWriteStatus, UNSET,
)


class KnowledgeWriter(Protocol):
    def create_explicit_knowledge(self, request: ExplicitKnowledgeWriteRequest) -> KnowledgeWriteResult: ...
    def correct_knowledge(self, request: KnowledgeCorrectionRequest) -> KnowledgeWriteResult: ...


class PolicyControlledKnowledgeWriter:
    def __init__(self, store: KnowledgeStore, policy: KnowledgePolicy,
                 record_factory: KnowledgeRecordFactory,
                 timestamp_factory: Callable[[], datetime]) -> None:
        self._store, self._policy = store, policy
        self._record_factory, self._timestamp_factory = record_factory, timestamp_factory

    def create_explicit_knowledge(self, request: ExplicitKnowledgeWriteRequest) -> KnowledgeWriteResult:
        outcome = self._policy_outcome(self._policy.evaluate_creation(request))
        if outcome: return outcome
        record = self._record_factory.create(request.knowledge_type, request.content, request.source,
            source_request_id=request.source_request_id, title=request.title, tags=request.tags,
            metadata=request.metadata)
        try:
            return KnowledgeWriteResult(KnowledgeWriteStatus.CREATED, "created", self._store.create(record))
        except DuplicateKnowledgeError:
            return KnowledgeWriteResult(KnowledgeWriteStatus.FAILED, "duplicate_knowledge")
        except InvalidKnowledgeOperationError:
            return KnowledgeWriteResult(KnowledgeWriteStatus.FAILED, "invalid_knowledge_request")

    def correct_knowledge(self, request: KnowledgeCorrectionRequest) -> KnowledgeWriteResult:
        try:
            existing = self._store.get(request.target_knowledge_id)
        except KnowledgeNotFoundError:
            return KnowledgeWriteResult(KnowledgeWriteStatus.FAILED, "knowledge_not_found")
        outcome = self._policy_outcome(self._policy.evaluate_correction(existing, request))
        if outcome: return outcome
        replacement = KnowledgeRecord(existing.knowledge_id, existing.knowledge_type,
            request.replacement_content, request.source, existing.created_at,
            self._timestamp_factory(), request.source_request_id,
            self._value(request.title, existing.title), self._value(request.tags, existing.tags),
            existing.status, self._value(request.metadata, existing.metadata))
        try:
            return KnowledgeWriteResult(KnowledgeWriteStatus.UPDATED, "updated", self._store.update(replacement))
        except InvalidKnowledgeOperationError:
            return KnowledgeWriteResult(KnowledgeWriteStatus.FAILED, "invalid_knowledge_request")

    @staticmethod
    def _policy_outcome(result: object) -> KnowledgeWriteResult | None:
        if result.decision is KnowledgePolicyDecision.REJECTED:
            return KnowledgeWriteResult(KnowledgeWriteStatus.REJECTED, result.reason_code)
        if result.decision is KnowledgePolicyDecision.REQUIRES_CONFIRMATION:
            return KnowledgeWriteResult(KnowledgeWriteStatus.REQUIRES_CONFIRMATION, result.reason_code,
                                        requires_confirmation=True)
        return None

    @staticmethod
    def _value(requested: object, current: object) -> object:
        return current if requested is UNSET else requested
