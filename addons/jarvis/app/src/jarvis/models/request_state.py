"""Lifecycle states for orchestration requests."""

from enum import Enum


class RequestState(str, Enum):
    """The current orchestration stage of a RequestContext."""

    RECEIVED = "received"
    CLASSIFIED = "classified"
    CAPABILITIES_SELECTED = "capabilities_selected"
    CONTEXT_ASSEMBLED = "context_assembled"
    PLANNED = "planned"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
