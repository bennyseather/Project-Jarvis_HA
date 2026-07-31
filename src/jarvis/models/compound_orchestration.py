"""Provider-neutral contracts for bounded compound home orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from jarvis.models.home_assistant_gateway import HomeAssistantActionProposal


class CompoundStepStatus(str, Enum):
    SUCCEEDED = "succeeded"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class CompoundCondition:
    entity_id: str
    friendly_name: str
    expected_states: frozenset[str]


@dataclass(frozen=True, slots=True)
class CompoundPlanStep:
    step_id: str
    sequence: int
    proposal: HomeAssistantActionProposal
    friendly_names: tuple[str, ...]
    condition: CompoundCondition | None = None


@dataclass(frozen=True, slots=True)
class CompoundPlan:
    conversation_id: str
    steps: tuple[CompoundPlanStep, ...]
    summary: str


@dataclass(frozen=True, slots=True)
class CompoundStepOutcome:
    step_id: str
    status: CompoundStepStatus
    message: str
    entity_ids: tuple[str, ...] = ()
