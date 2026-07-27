"""Typed contracts for durable, bounded short-term conversation memory."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class StoredConversationMessage:
    message_id: int
    conversation_id: str
    role: str
    content: str
    created_at: datetime

    def to_openai(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass(frozen=True, slots=True)
class RepeatedContextCandidate:
    key: str
    content: str
    category: str
    is_sensitive: bool = False
