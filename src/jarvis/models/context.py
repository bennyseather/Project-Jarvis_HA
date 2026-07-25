"""Models describing context assembled for Jarvis orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping

from jarvis.models.chat_message import ChatMessage
from jarvis.models.memory import MemorySource, MemoryType
from jarvis.models.knowledge import KnowledgeSource, KnowledgeType


@dataclass(frozen=True, slots=True)
class MemoryContextMatch:
    """A retrieval-safe memory item made available to orchestration."""

    content: str
    memory_type: MemoryType
    tags: tuple[str, ...]
    source: MemorySource
    retrieval_score: float


@dataclass(frozen=True, slots=True)
class MemoryContext:
    """The bounded, typed memory portion of an assembled context package."""

    matches: tuple[MemoryContextMatch, ...]
    result_limit: int

@dataclass(frozen=True, slots=True)
class KnowledgeContextMatch:
    content: str; title: str | None; knowledge_type: KnowledgeType; tags: tuple[str, ...]; source: KnowledgeSource; retrieval_score: float

@dataclass(frozen=True, slots=True)
class KnowledgeContext:
    matches: tuple[KnowledgeContextMatch, ...]; result_limit: int


@dataclass(frozen=True, slots=True)
class ContextPackage:
    """Contextual information available to an orchestration request."""

    conversation: tuple[ChatMessage, ...] | None = None
    memory: MemoryContext | None = None
    home_assistant: Mapping[str, object] | None = None
    knowledge: KnowledgeContext | None = None
    time: datetime | None = None
    metadata: Mapping[str, object] | None = None
