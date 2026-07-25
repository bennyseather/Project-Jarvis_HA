"""Models describing planned and completed execution work."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping

from jarvis.models.capability import Capability, CapabilityProvider


class ExecutionStatus(str, Enum):
    """The outcome of executing an ExecutionPlan."""

    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    NOT_SUPPORTED = "not_supported"


@dataclass(frozen=True, slots=True)
class ExecutionStep:
    """One ordered, provider-neutral unit of planned work."""

    name: str
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    """A declarative plan for execution without provider-specific logic."""

    selected_capability: Capability | None = None
    selected_provider: CapabilityProvider | None = None
    steps: tuple[ExecutionStep, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)
    requires_confirmation: bool = False
    parallel_execution: bool = False


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """The structured outcome returned by an execution pipeline."""

    status: ExecutionStatus
    message: str
    metadata: Mapping[str, object] = field(default_factory=dict)
    error: str | None = None
