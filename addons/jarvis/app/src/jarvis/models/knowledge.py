"""Provider-neutral contracts for curated Jarvis knowledge."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4


class KnowledgeType(str, Enum):
    HOME_REFERENCE = "home_reference"
    ROOM_DOCUMENTATION = "room_documentation"
    DEVICE_DOCUMENTATION = "device_documentation"
    HOUSEHOLD_PROCEDURE = "household_procedure"
    PROJECT_DOCUMENTATION = "project_documentation"
    USER_APPROVED_REFERENCE = "user_approved_reference"


class KnowledgeSource(str, Enum):
    USER_PROVIDED = "user_provided"
    USER_APPROVED_DOCUMENT = "user_approved_document"
    USER_APPROVED_IMPORT = "user_approved_import"


class KnowledgeStatus(str, Enum):
    ACTIVE = "active"
    PENDING_APPROVAL = "pending_approval"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class KnowledgeRecord:
    knowledge_id: str
    knowledge_type: KnowledgeType
    content: str
    source: KnowledgeSource
    created_at: datetime
    updated_at: datetime
    source_request_id: str | None = None
    title: str | None = None
    tags: tuple[str, ...] = ()
    status: KnowledgeStatus = KnowledgeStatus.ACTIVE
    metadata: Mapping[str, object] = field(default_factory=dict)


class KnowledgeRecordFactory:
    """Create records with injectable identity and timestamp sources."""

    def __init__(self, knowledge_id_factory: Callable[[], str] | None = None,
                 timestamp_factory: Callable[[], datetime] | None = None) -> None:
        self._knowledge_id_factory = knowledge_id_factory or (lambda: str(uuid4()))
        self._timestamp_factory = timestamp_factory or (lambda: datetime.now(timezone.utc))

    def create(self, knowledge_type: KnowledgeType, content: str, source: KnowledgeSource,
               *, source_request_id: str | None = None, title: str | None = None,
               tags: tuple[str, ...] = (), status: KnowledgeStatus = KnowledgeStatus.ACTIVE,
               metadata: Mapping[str, object] | None = None) -> KnowledgeRecord:
        timestamp = self._timestamp_factory()
        return KnowledgeRecord(self._knowledge_id_factory(), knowledge_type, content, source,
                               timestamp, timestamp, source_request_id, title, tags, status,
                               {} if metadata is None else metadata)
