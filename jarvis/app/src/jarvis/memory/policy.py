"""Provider-neutral policy contracts for explicit memory writing."""

from __future__ import annotations

from typing import Protocol

from jarvis.models.memory import (
    MemoryConsentLevel,
    MemoryRecord,
    MemorySource,
    MemoryStatus,
    MemoryType,
)
from jarvis.models.memory_retrieval import (
    MemoryRetrievalEligibility,
    MemoryRetrievalPolicyResult,
    MemoryRetrievalQuery,
)
from jarvis.models.memory_management import (
    MemoryManagementAction,
    MemoryManagementEligibility,
    MemoryManagementPolicyResult,
    MemoryManagementRequest,
)
from jarvis.models.memory_write import (
    ExplicitMemoryWriteRequest,
    MemoryCorrectionRequest,
    MemoryPolicyDecision,
    MemoryPolicyResult,
)


class MemoryPolicy(Protocol):
    """Decides whether explicit memory operations may be persisted."""

    def evaluate_creation(
        self,
        request: ExplicitMemoryWriteRequest,
    ) -> MemoryPolicyResult:
        """Evaluate a proposed explicit-memory creation."""

    def evaluate_correction(
        self,
        record: MemoryRecord,
        request: MemoryCorrectionRequest,
    ) -> MemoryPolicyResult:
        """Evaluate a proposed correction of an existing memory."""

    def evaluate_retrieval(
        self,
        record: MemoryRecord,
        query: MemoryRetrievalQuery,
    ) -> MemoryRetrievalPolicyResult:
        """Evaluate whether one stored record may be considered for retrieval."""

    def evaluate_management(
        self,
        record: MemoryRecord,
        request: MemoryManagementRequest,
    ) -> MemoryManagementPolicyResult:
        """Evaluate whether one record may be inspected or managed."""


class ExplicitMemoryPolicy:
    """Deterministic policy for approved explicit-memory operations."""

    _ELIGIBLE_TYPES = {
        MemoryType.PREFERENCE,
        MemoryType.FACT,
        MemoryType.INSTRUCTION,
        MemoryType.PROJECT,
    }

    def evaluate_creation(
        self,
        request: ExplicitMemoryWriteRequest,
    ) -> MemoryPolicyResult:
        """Approve only explicit, eligible, appropriately confirmed requests."""

        if request.source is MemorySource.REPEATED_USER_CONTEXT:
            return self._evaluate(
                True,
                request.is_sensitive,
                request.has_sensitive_confirmation,
                request.memory_type,
            )
        if request.source is not MemorySource.EXPLICIT_USER_REQUEST:
            return self._rejected("invalid_creation_source")
        return self._evaluate(
            request.is_explicit,
            request.is_sensitive,
            request.has_sensitive_confirmation,
            request.memory_type,
        )

    def evaluate_correction(
        self,
        record: MemoryRecord,
        request: MemoryCorrectionRequest,
    ) -> MemoryPolicyResult:
        """Apply the same explicit-consent rules to a correction."""

        if request.source is not MemorySource.USER_CORRECTION:
            return self._rejected("invalid_correction_source")
        return self._evaluate(
            request.is_explicit,
            request.is_sensitive,
            request.has_sensitive_confirmation,
            record.memory_type,
        )

    def evaluate_retrieval(
        self,
        record: MemoryRecord,
        query: MemoryRetrievalQuery,
    ) -> MemoryRetrievalPolicyResult:
        """Apply lifecycle, consent, type, expiry, and sensitivity eligibility."""

        if record.status is not MemoryStatus.ACTIVE:
            return self._ineligible("memory_not_active")
        if record.memory_type not in self._ELIGIBLE_TYPES:
            return self._ineligible("reserved_memory_type")
        if record.expires_at is not None and query.evaluation_time is not None:
            if record.expires_at <= query.evaluation_time:
                return self._ineligible("memory_expired")
        if (
            record.consent_level is MemoryConsentLevel.SENSITIVE_CONFIRMED
            and not query.include_sensitive
        ):
            return self._ineligible("sensitive_memory_not_requested")
        return MemoryRetrievalPolicyResult(
            MemoryRetrievalEligibility.ELIGIBLE,
            "eligible",
        )

    def evaluate_management(
        self,
        record: MemoryRecord,
        request: MemoryManagementRequest,
    ) -> MemoryManagementPolicyResult:
        """Allow only explicit, policy-approved memory management."""

        if not request.is_explicit:
            return self._management_ineligible("explicit_management_required")
        if record.status is not MemoryStatus.ACTIVE:
            return self._management_ineligible("memory_not_active")
        if record.memory_type not in self._ELIGIBLE_TYPES:
            return self._management_ineligible("reserved_memory_type")
        if record.consent_level is MemoryConsentLevel.SENSITIVE_CONFIRMED:
            if not request.query.include_sensitive:
                return self._management_ineligible("sensitive_memory_not_requested")
            if (
                request.action
                not in {
                    MemoryManagementAction.DELETE_MATCHES,
                    MemoryManagementAction.DELETE_ALL,
                }
                and not request.has_confirmation
            ):
                return self._management_ineligible(
                    "sensitive_management_confirmation_required"
                )
        return MemoryManagementPolicyResult(
            MemoryManagementEligibility.ELIGIBLE,
            "eligible",
        )

    def _evaluate(
        self,
        is_explicit: bool,
        is_sensitive: bool,
        has_sensitive_confirmation: bool,
        memory_type: MemoryType,
    ) -> MemoryPolicyResult:
        if not is_explicit:
            return self._rejected("explicit_consent_required")
        if memory_type not in self._ELIGIBLE_TYPES:
            return self._rejected("reserved_memory_type")
        if is_sensitive and not has_sensitive_confirmation:
            return MemoryPolicyResult(
                MemoryPolicyDecision.REQUIRES_CONFIRMATION,
                "sensitive_confirmation_required",
            )
        return MemoryPolicyResult(MemoryPolicyDecision.APPROVED, "approved")

    @staticmethod
    def _rejected(reason_code: str) -> MemoryPolicyResult:
        return MemoryPolicyResult(MemoryPolicyDecision.REJECTED, reason_code)

    @staticmethod
    def _ineligible(reason_code: str) -> MemoryRetrievalPolicyResult:
        return MemoryRetrievalPolicyResult(
            MemoryRetrievalEligibility.INELIGIBLE,
            reason_code,
        )

    @staticmethod
    def _management_ineligible(reason_code: str) -> MemoryManagementPolicyResult:
        return MemoryManagementPolicyResult(
            MemoryManagementEligibility.INELIGIBLE,
            reason_code,
        )
