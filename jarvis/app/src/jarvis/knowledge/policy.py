"""Provider-neutral policy contracts for explicit Knowledge writing."""

from __future__ import annotations

from typing import Protocol

from jarvis.models.knowledge import KnowledgeRecord, KnowledgeSource, KnowledgeType
from jarvis.models.knowledge_write import (
    ExplicitKnowledgeWriteRequest, KnowledgeCorrectionRequest, KnowledgePolicyDecision,
    KnowledgePolicyResult,
)
from jarvis.models.knowledge_retrieval import KnowledgeRetrievalEligibility, KnowledgeRetrievalPolicyResult, KnowledgeRetrievalQuery


class KnowledgePolicy(Protocol):
    def evaluate_creation(self, request: ExplicitKnowledgeWriteRequest) -> KnowledgePolicyResult: ...
    def evaluate_correction(self, record: KnowledgeRecord,
                            request: KnowledgeCorrectionRequest) -> KnowledgePolicyResult: ...
    def evaluate_retrieval(self, record: KnowledgeRecord, query: KnowledgeRetrievalQuery) -> KnowledgeRetrievalPolicyResult: ...


class ExplicitKnowledgePolicy:
    """Approve only explicitly approved, non-sensitive Knowledge writes."""

    _TYPES = frozenset(KnowledgeType)
    _SOURCES = frozenset(KnowledgeSource)

    def evaluate_creation(self, request: ExplicitKnowledgeWriteRequest) -> KnowledgePolicyResult:
        return self._evaluate(request.is_explicitly_approved, request.is_sensitive,
                              request.knowledge_type, request.source)

    def evaluate_correction(self, record: KnowledgeRecord,
                            request: KnowledgeCorrectionRequest) -> KnowledgePolicyResult:
        return self._evaluate(request.is_explicitly_approved, request.is_sensitive,
                              record.knowledge_type, request.source)

    def evaluate_retrieval(self, record: KnowledgeRecord, query: KnowledgeRetrievalQuery) -> KnowledgeRetrievalPolicyResult:
        from jarvis.models.knowledge import KnowledgeStatus
        if record.status is not KnowledgeStatus.ACTIVE: return KnowledgeRetrievalPolicyResult(KnowledgeRetrievalEligibility.INELIGIBLE,"knowledge_not_active")
        if record.knowledge_type not in self._TYPES or record.source not in self._SOURCES: return KnowledgeRetrievalPolicyResult(KnowledgeRetrievalEligibility.INELIGIBLE,"knowledge_not_approved")
        return KnowledgeRetrievalPolicyResult(KnowledgeRetrievalEligibility.ELIGIBLE,"eligible")

    @classmethod
    def _evaluate(cls, is_explicitly_approved: bool, is_sensitive: bool,
                  knowledge_type: object, source: object) -> KnowledgePolicyResult:
        if not is_explicitly_approved:
            return KnowledgePolicyResult(KnowledgePolicyDecision.REJECTED, "explicit_approval_required")
        if knowledge_type not in cls._TYPES:
            return KnowledgePolicyResult(KnowledgePolicyDecision.REJECTED, "unsupported_knowledge_type")
        if source not in cls._SOURCES:
            return KnowledgePolicyResult(KnowledgePolicyDecision.REJECTED, "unsupported_knowledge_source")
        if is_sensitive:
            return KnowledgePolicyResult(KnowledgePolicyDecision.REJECTED, "sensitive_knowledge_not_supported")
        return KnowledgePolicyResult(KnowledgePolicyDecision.APPROVED, "approved")
