"""Models used to describe and classify incoming user requests."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RequestType(str, Enum):
    """Categories used to select a future orchestration path."""

    INFORMATION = "information"
    COMMAND = "command"
    QUERY = "query"
    AUTOMATION = "automation"
    PLANNING = "planning"
    MEMORY = "memory"
    CONVERSATION = "conversation"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class Request:
    """An incoming user request preserved for downstream processing."""

    content: str


@dataclass(frozen=True, slots=True)
class RequestClassification:
    """The classification outcome for an incoming request."""

    request: Request
    request_type: RequestType
