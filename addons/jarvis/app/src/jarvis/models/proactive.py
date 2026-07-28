"""Typed contracts for bounded, explainable proactive assistance."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Mapping


class ProactiveSuggestionKind(str, Enum):
    ATTENTION = "attention"
    FOLLOW_UP = "follow_up"
    ROUTINE = "routine"


class ProactiveSuggestionStatus(str, Enum):
    PENDING = "pending"
    SNOOZED = "snoozed"
    ACCEPTED = "accepted"
    DISMISSED = "dismissed"
    EXPIRED = "expired"
    CLEARED = "cleared"


class ProactiveDisposition(str, Enum):
    ACCEPT = "accept"
    NOT_NOW = "not_now"
    DISMISS = "dismiss"
    SUPPRESS = "suppress"


@dataclass(frozen=True, slots=True)
class ProactiveCandidate:
    kind: ProactiveSuggestionKind
    subject: str
    message: str
    reason: str
    confidence: float
    source_ids: tuple[str, ...] = ()
    sensitive: bool = False
    action: Mapping[str, object] | None = None


@dataclass(frozen=True, slots=True)
class ProactiveSuggestion:
    suggestion_id: str
    kind: ProactiveSuggestionKind
    subject: str
    message: str
    reason: str
    confidence: float
    source_ids: tuple[str, ...]
    sensitive: bool
    action: Mapping[str, object] | None
    status: ProactiveSuggestionStatus
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    snoozed_until: datetime | None = None
    delivered_channels: tuple[str, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)

