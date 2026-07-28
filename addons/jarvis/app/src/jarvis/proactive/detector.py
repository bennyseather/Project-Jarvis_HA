"""Deterministic opportunity detection over approved, bounded inputs."""

from __future__ import annotations

from collections import Counter

from jarvis.models.proactive import ProactiveCandidate, ProactiveSuggestionKind
from jarvis.models.reflection import ReflectionKind


class ProactiveOpportunityDetector:
    """Produce suggestions without model inference or permanent profiling."""

    def __init__(
        self, *, low_battery_threshold: int = 20, routine_repeat_threshold: int = 3
    ) -> None:
        self._low_battery = low_battery_threshold
        self._repeat = routine_repeat_threshold

    def detect(
        self, *, states=(), timeline_events=(), reflections=()
    ) -> tuple[ProactiveCandidate, ...]:
        candidates = [
            *self._battery_candidates(states),
            *self._reflection_candidates(reflections),
            *self._routine_candidates(timeline_events),
        ]
        return tuple(sorted(
            candidates,
            key=lambda item: (-item.confidence, item.kind.value, item.subject),
        ))

    def _battery_candidates(self, states):
        found = []
        for state in states:
            entity_id, raw, attributes = self._state_parts(state)
            if not entity_id.startswith("sensor."):
                continue
            device_class = str(attributes.get("device_class", "")).casefold()
            if device_class != "battery" and "battery" not in entity_id.casefold():
                continue
            try:
                level = float(raw)
            except (TypeError, ValueError):
                continue
            if level > self._low_battery:
                continue
            name = str(attributes.get("friendly_name") or entity_id)
            found.append(ProactiveCandidate(
                ProactiveSuggestionKind.ATTENTION,
                f"low-battery:{entity_id}",
                f"{name} has a low battery at {level:g} percent.",
                (
                    f"Home Assistant reports {entity_id} at or below the configured "
                    f"{self._low_battery} percent threshold."
                ),
                1.0,
                (entity_id,),
            ))
        return found

    @staticmethod
    def _reflection_candidates(reflections):
        found = []
        for record in reflections:
            if record.sensitive:
                continue
            if record.kind not in {
                ReflectionKind.FOLLOW_UP,
                ReflectionKind.CONTRADICTION,
                ReflectionKind.UNCERTAINTY,
            }:
                continue
            found.append(ProactiveCandidate(
                ProactiveSuggestionKind.FOLLOW_UP,
                f"reflection:{record.reflection_id}",
                record.content,
                "This follows from inspectable, approved memory reflection.",
                record.confidence,
                tuple(record.source_memory_ids),
            ))
        return found

    def _routine_candidates(self, events):
        counts = Counter(
            (event.entity_id, event.state)
            for event in events
            if event.state not in {None, "unknown", "unavailable"}
        )
        found = []
        for (entity_id, state), count in sorted(counts.items()):
            if count < self._repeat:
                continue
            found.append(ProactiveCandidate(
                ProactiveSuggestionKind.ROUTINE,
                f"routine:{entity_id}:{state}",
                (
                    f"{entity_id} has changed to {state} {count} times in the "
                    "bounded recent event window. Would you like to review a routine?"
                ),
                (
                    "This is a temporary routine candidate based only on the "
                    "configured in-memory Home Assistant event timeline."
                ),
                min(1.0, 0.7 + 0.05 * count),
                tuple(
                    str(event.event_id)
                    for event in events
                    if event.entity_id == entity_id and event.state == state
                ),
            ))
        return found

    @staticmethod
    def _state_parts(state):
        if isinstance(state, dict):
            return (
                str(state.get("entity_id", "")),
                state.get("state"),
                state.get("attributes", {})
                if isinstance(state.get("attributes"), dict) else {},
            )
        return (
            str(getattr(state, "entity_id", "")),
            getattr(state, "state", None),
            getattr(state, "attributes", {}) or {},
        )

