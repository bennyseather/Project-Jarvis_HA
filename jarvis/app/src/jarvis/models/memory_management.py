"""Provider-neutral contracts for explicit memory management."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from jarvis.models.memory import MemoryRecord, MemoryType


class MemoryManagementAction(str, Enum):
    """Explicit operations supported by the memory-management boundary."""

    INSPECT = "inspect"
    LIST = "list"
    FIND = "find"
    DELETE_ONE = "delete_one"
    DELETE_MATCHES = "delete_matches"
    DELETE_ALL = "delete_all"


class MemoryManagementStatus(str, Enum):
    """Distinct outcomes for a memory-management operation."""

    SUCCESS = "success"
    NO_MATCH = "no_match"
    REQUIRES_CONFIRMATION = "requires_confirmation"
    REJECTED = "rejected"
    FAILED = "failed"
    PARTIAL = "partial"


class MemoryManagementEligibility(str, Enum):
    """Policy eligibility outcomes for one management target."""

    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"


@dataclass(frozen=True, slots=True)
class MemoryManagementQuery:
    """Deterministic filters for an explicit management operation."""

    memory_id: str | None = None
    exact_content: str | None = None
    memory_types: frozenset[MemoryType] = field(default_factory=frozenset)
    tags: tuple[str, ...] = ()
    maximum_results: int = 10
    include_sensitive: bool = False

    def __post_init__(self) -> None:
        if not 0 <= self.maximum_results <= 10:
            raise ValueError("maximum_results must be between 0 and 10.")


@dataclass(frozen=True, slots=True)
class MemoryManagementRequest:
    """An explicit request to inspect or manage durable memory."""

    action: MemoryManagementAction
    query: MemoryManagementQuery
    source_request_id: str | None = None
    is_explicit: bool = True
    has_confirmation: bool = False
    confirmation_token: str | None = None


@dataclass(frozen=True, slots=True)
class MemoryManagementPolicyResult:
    """One policy decision about management access to a stored record."""

    eligibility: MemoryManagementEligibility
    reason_code: str


@dataclass(frozen=True, slots=True)
class MemoryManagementCandidate:
    """A non-content target summary used to resolve ambiguity safely."""

    memory_id: str
    memory_type: MemoryType
    tags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MemoryManagementResult:
    """A transient, non-content outcome for a management operation."""

    status: MemoryManagementStatus
    reason_code: str
    candidates: tuple[MemoryManagementCandidate, ...] = ()
    deleted_memory_ids: tuple[str, ...] = ()
    deleted_count: int = 0
    requires_confirmation: bool = False
    confirmation_token: str | None = None
    record: MemoryRecord | None = None
