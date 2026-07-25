"""Bounded, process-local storage for approved timeline events."""
from __future__ import annotations
from collections import deque
from jarvis.models.event_timeline import TimelineEvent, TimelineQuery


class InMemoryTimelineStore:
    def __init__(self, max_events: int = 50):
        if not isinstance(max_events, int) or isinstance(max_events, bool) or max_events < 1:
            raise ValueError("max_events must be a positive integer")
        self._events = deque(maxlen=max_events)
        self._next_id = 1

    def append(self, event_type, entity_id, occurred_at, state=None) -> TimelineEvent:
        event = TimelineEvent(self._next_id, event_type, entity_id, occurred_at, state)
        self._next_id += 1
        self._events.append(event)
        return event

    def retrieve(self, query: TimelineQuery) -> tuple[TimelineEvent, ...]:
        if not 1 <= query.maximum_results <= 50:
            raise ValueError("maximum_results must be between 1 and 50")
        events = (event for event in reversed(self._events)
                  if (query.entity_id is None or event.entity_id == query.entity_id)
                  and (query.event_type is None or event.event_type == query.event_type))
        return tuple(list(events)[:query.maximum_results])
