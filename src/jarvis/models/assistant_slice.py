"""Typed provider-neutral contracts for the first Jarvis vertical slice."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Protocol


class AssistantProposalKind(str, Enum):
    CONVERSATION = "conversation"
    READ_ENTITY_STATE = "read_entity_state"
    UNSUPPORTED = "unsupported"
    HOME_ASSISTANT_ACTION = "home_assistant_action"


@dataclass(frozen=True, slots=True)
class AssistantInput:
    request_text: str
    context: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AssistantProposal:
    kind: AssistantProposalKind
    message: str = ""
    entity_id: str | None = None
    action: Mapping[str, object] | None = None


@dataclass(frozen=True, slots=True)
class HomeAssistantState:
    entity_id: str
    state: str
    attributes: Mapping[str, object] = field(default_factory=dict)


class LanguageModelProvider(Protocol):
    def propose(self, request: AssistantInput) -> AssistantProposal: ...


class HomeAssistantReadProvider(Protocol):
    async def read_entity_state(self, entity_id: str) -> HomeAssistantState: ...
