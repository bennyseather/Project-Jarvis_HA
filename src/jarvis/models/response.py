"""Provider-neutral response models for orchestration outcomes."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Mapping


class ResponseStatus(str, Enum):
    """Normalized status values exposed by a Response."""

    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    NOT_SUPPORTED = "not_supported"


@dataclass(frozen=True, slots=True)
class FollowUpAction:
    """A provider-neutral action a presentation layer may offer."""

    name: str
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ConfirmationRequest:
    """A confirmation a presentation layer may request from a user."""

    action: str
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Response:
    """A normalized, provider-neutral outcome for presentation layers."""

    status: ResponseStatus
    summary: str
    timestamp: datetime
    detailed_message: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)
    follow_up_actions: tuple[FollowUpAction, ...] = ()
    confirmation_request: ConfirmationRequest | None = None
