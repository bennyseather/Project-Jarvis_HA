"""Deny-by-default policy for non-durable event awareness."""
from __future__ import annotations


class EventTimelinePolicy:
    def __init__(self, enabled=False, allowed_event_types=(), allowed_entities=()):
        self.enabled = enabled
        self._types = frozenset(allowed_event_types)
        self._entities = frozenset(allowed_entities)

    def permits(self, event_type: str, entity_id: str) -> bool:
        return self.enabled and event_type in self._types and entity_id in self._entities
