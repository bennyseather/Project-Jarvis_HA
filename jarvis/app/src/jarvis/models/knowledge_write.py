"""Contracts for policy-controlled explicit Knowledge writing."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum

from jarvis.models.knowledge import KnowledgeRecord, KnowledgeSource, KnowledgeType


class _Unset:
    def __repr__(self) -> str: return "UNSET"


UNSET = _Unset()
UnsetType = _Unset


class KnowledgePolicyDecision(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    REQUIRES_CONFIRMATION = "requires_confirmation"


class KnowledgeWriteStatus(str, Enum):
    CREATED = "created"
    UPDATED = "updated"
    REJECTED = "rejected"
    REQUIRES_CONFIRMATION = "requires_confirmation"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ExplicitKnowledgeWriteRequest:
    content: str
    knowledge_type: KnowledgeType
    source: KnowledgeSource
    source_request_id: str | None = None
    title: str | None = None
    tags: tuple[str, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)
    is_explicitly_approved: bool = True
    is_sensitive: bool = False


@dataclass(frozen=True, slots=True)
class KnowledgeCorrectionRequest:
    target_knowledge_id: str
    replacement_content: str
    source: KnowledgeSource
    source_request_id: str | None = None
    title: str | None | UnsetType = UNSET
    tags: tuple[str, ...] | UnsetType = UNSET
    metadata: Mapping[str, object] | UnsetType = UNSET
    is_explicitly_approved: bool = True
    is_sensitive: bool = False


@dataclass(frozen=True, slots=True)
class KnowledgePolicyResult:
    decision: KnowledgePolicyDecision
    reason_code: str


@dataclass(frozen=True, slots=True)
class KnowledgeWriteResult:
    status: KnowledgeWriteStatus
    reason_code: str
    record: KnowledgeRecord | None = None
    requires_confirmation: bool = False
