"""Contracts for policy-controlled explicit memory writing."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from jarvis.models.memory import (
    MemoryConsentLevel,
    MemoryRecord,
    MemorySource,
    MemoryType,
)


class _Unset:
    """A dedicated value representing an omitted correction field."""

    def __repr__(self) -> str:
        return "UNSET"


UNSET = _Unset()
UnsetType = _Unset


class MemoryPolicyDecision(str, Enum):
    """A policy outcome for a proposed memory write."""

    APPROVED = "approved"
    REQUIRES_CONFIRMATION = "requires_confirmation"
    REJECTED = "rejected"


class MemoryWriteStatus(str, Enum):
    """The result of a memory-writing operation."""

    CREATED = "created"
    UPDATED = "updated"
    REQUIRES_CONFIRMATION = "requires_confirmation"
    REJECTED = "rejected"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ExplicitMemoryWriteRequest:
    """A user-requested proposal to create durable memory."""

    content: str
    memory_type: MemoryType
    source: MemorySource
    consent_level: MemoryConsentLevel
    source_request_id: str | None = None
    is_explicit: bool = True
    is_sensitive: bool = False
    has_sensitive_confirmation: bool = False
    tags: tuple[str, ...] = ()
    importance: float | None = None
    confidence: float | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MemoryCorrectionRequest:
    """A user-requested replacement of an existing memory value."""

    target_memory_id: str
    replacement_content: str
    source: MemorySource
    consent_level: MemoryConsentLevel
    source_request_id: str | None = None
    is_explicit: bool = True
    is_sensitive: bool = False
    has_sensitive_confirmation: bool = False
    expires_at: datetime | None | UnsetType = UNSET
    tags: tuple[str, ...] | UnsetType = UNSET
    importance: float | None | UnsetType = UNSET
    confidence: float | None | UnsetType = UNSET
    metadata: Mapping[str, object] | UnsetType = UNSET


@dataclass(frozen=True, slots=True)
class MemoryPolicyResult:
    """A typed policy decision with a stable reason code."""

    decision: MemoryPolicyDecision
    reason_code: str


@dataclass(frozen=True, slots=True)
class MemoryWriteResult:
    """The structured outcome of a create or correction operation."""

    status: MemoryWriteStatus
    reason_code: str
    record: MemoryRecord | None = None
    requires_confirmation: bool = False
    metadata: Mapping[str, object] = field(default_factory=dict)
