"""
Models representing the structured response returned by the AI.

These models define the contract between the language model
and the rest of Jarvis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class AssistantAction:
    """
    One action proposed by the AI.

    The capability identifies which capability should execute,
    while parameters contains the arguments passed to it.
    """

    capability: str

    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AssistantMemory:
    """
    One memory item proposed by the AI.
    """

    type: str
    key: str
    value: str


@dataclass(slots=True)
class AssistantResponse:
    """
    Structured response returned by the AI.
    """

    thought: str

    response: str

    actions: list[AssistantAction] = field(default_factory=list)

    memory: list[AssistantMemory] = field(default_factory=list)

    questions: list[str] = field(default_factory=list)