"""Inspectable contracts for privacy-bounded reflective learning."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class ReflectionKind(str, Enum):
    RELATION = "relation"
    UNCERTAINTY = "uncertainty"
    CONTRADICTION = "contradiction"
    STYLE = "style"
    FOLLOW_UP = "follow_up"


@dataclass(frozen=True, slots=True)
class ReflectionRecord:
    reflection_id: str
    kind: ReflectionKind
    subject: str
    content: str
    confidence: float
    source_memory_ids: tuple[str, ...]
    source_conversation_ids: tuple[str, ...]
    sensitive: bool
    created_at: datetime
    updated_at: datetime
