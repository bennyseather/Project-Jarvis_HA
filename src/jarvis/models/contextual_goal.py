"""Contracts for explicit, inspectable household goal meanings."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ContextualGoal:
    goal_id: str
    name: str
    command: str
    confidence: float = 1.0


@dataclass(frozen=True, slots=True)
class GoalInterpretation:
    goal: ContextualGoal
    evidence: tuple[str, ...]
    assumptions: tuple[str, ...]
    explanation: str

