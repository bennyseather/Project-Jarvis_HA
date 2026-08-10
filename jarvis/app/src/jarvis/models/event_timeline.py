"""Provider-neutral, ephemeral Home Assistant event timeline contracts."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class TimelineEvent:
    event_id: int
    event_type: str
    entity_id: str
    occurred_at: datetime
    state: str | None = None


@dataclass(frozen=True, slots=True)
class TimelineQuery:
    entity_id: str | None = None
    event_type: str | None = None
    maximum_results: int = 10
