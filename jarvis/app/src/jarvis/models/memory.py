"""Provider-neutral contracts for durable Jarvis memory."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4


class MemoryType(str, Enum):
    """Categories of information that may be represented as memory."""

    PREFERENCE = "preference"
    FACT = "fact"
    INSTRUCTION = "instruction"
    PROJECT = "project"
    EPISODIC = "episodic"
    CONVERSATION_SUMMARY = "conversation_summary"


class MemoryStatus(str, Enum):
    """States a memory record may have before hard deletion."""

    ACTIVE = "active"
    SUPERSEDED = "superseded"
    EXPIRED = "expired"
    PENDING_CONFIRMATION = "pending_confirmation"
    REJECTED = "rejected"


class MemorySource(str, Enum):
    """The provenance category for a memory record."""

    EXPLICIT_USER_REQUEST = "explicit_user_request"
    USER_CORRECTION = "user_correction"
    CONVERSATION_SUMMARY = "conversation_summary"
    PROJECT_DOCUMENT = "project_document"
    IMPORTED_KNOWLEDGE = "imported_knowledge"
    LEARNED_PREFERENCE = "learned_preference"
    REPEATED_USER_CONTEXT = "repeated_user_context"


class MemoryConsentLevel(str, Enum):
    """The consent basis associated with a memory record."""

    EXPLICIT = "explicit"
    SENSITIVE_CONFIRMED = "sensitive_confirmed"
    AUTOMATIC_LOW_SENSITIVITY = "automatic_low_sensitivity"


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    """A provider-neutral durable-memory record."""

    memory_id: str
    memory_type: MemoryType
    content: str
    source: MemorySource
    consent_level: MemoryConsentLevel
    created_at: datetime
    updated_at: datetime
    source_request_id: str | None = None
    expires_at: datetime | None = None
    importance: float | None = None
    confidence: float | None = None
    tags: tuple[str, ...] = ()
    status: MemoryStatus = MemoryStatus.ACTIVE
    metadata: Mapping[str, object] = field(default_factory=dict)


class MemoryRecordFactory:
    """Create memory records with injectable identity and time sources."""

    def __init__(
        self,
        memory_id_factory: Callable[[], str] | None = None,
        timestamp_factory: Callable[[], datetime] | None = None,
    ) -> None:
        self._memory_id_factory = memory_id_factory or self._default_memory_id
        self._timestamp_factory = timestamp_factory or self._default_timestamp

    def create(
        self,
        memory_type: MemoryType,
        content: str,
        source: MemorySource,
        consent_level: MemoryConsentLevel,
        *,
        source_request_id: str | None = None,
        expires_at: datetime | None = None,
        importance: float | None = None,
        confidence: float | None = None,
        tags: tuple[str, ...] = (),
        status: MemoryStatus = MemoryStatus.ACTIVE,
        metadata: Mapping[str, object] | None = None,
    ) -> MemoryRecord:
        """Create a record with one timestamp for both initial time fields."""

        timestamp = self._timestamp_factory()
        return MemoryRecord(
            memory_id=self._memory_id_factory(),
            memory_type=memory_type,
            content=content,
            source=source,
            consent_level=consent_level,
            created_at=timestamp,
            updated_at=timestamp,
            source_request_id=source_request_id,
            expires_at=expires_at,
            importance=importance,
            confidence=confidence,
            tags=tags,
            status=status,
            metadata={} if metadata is None else metadata,
        )

    @staticmethod
    def _default_memory_id() -> str:
        return str(uuid4())

    @staticmethod
    def _default_timestamp() -> datetime:
        return datetime.now(timezone.utc)
