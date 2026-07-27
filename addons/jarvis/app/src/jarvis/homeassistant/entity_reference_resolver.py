"""Deterministic, authorization-bounded Home Assistant reference resolution."""
from __future__ import annotations


class EntityReferenceResolver:
    """Resolve exact entities and explicitly named collectives without guessing."""

    def __init__(
        self,
        allowed_entity_ids,
        aliases=None,
        friendly_names=None,
        areas=None,
        groups=None,
    ):
        self._ids = frozenset(allowed_entity_ids)
        self._areas = self._collectives(areas or {})
        self._groups = self._collectives(groups or {})
        self._names: dict[str, set[str]] = {}
        self._descriptive_names: set[str] = set()

        for entity_id in self._ids:
            self._add_name(entity_id, entity_id)
            self._add_name(entity_id.replace(".", " ").replace("_", " "), entity_id)
        for name, entity_id in (aliases or {}).items():
            self._add_name(name, entity_id)
            self._descriptive_names.add(self._norm(name))
        for name, targets in (friendly_names or {}).items():
            self._descriptive_names.add(self._norm(name))
            if isinstance(targets, str):
                targets = (targets,)
            for entity_id in targets:
                self._add_name(name, entity_id)

    def resolve(self, reference, domain: str | None = None):
        normalized = self._norm(reference)
        matches = self._areas.get(normalized) or self._groups.get(normalized)
        if matches is None:
            matches = self._names.get(normalized, ())
        return tuple(sorted(
            entity_id for entity_id in matches
            if entity_id in self._ids
            and (domain is None or entity_id.partition(".")[0] == domain)
        ))

    def is_collective(self, reference) -> bool:
        normalized = self._norm(reference)
        return normalized in self._areas or normalized in self._groups

    def candidates(self, reference, limit: int = 5):
        return self.resolve(reference)[:limit]

    def find_in_text(self, text):
        """Return the longest configured reference explicitly present in text."""
        normalized_text = self._norm(text)
        references = set(self._areas) | set(self._groups) | set(self._names)
        matches = [
            reference for reference in references
            if self._contains_reference(normalized_text, reference)
            and self.resolve(reference)
        ]
        if matches:
            reference = max(matches, key=lambda value: (len(value.split()), len(value), value))
            return reference, self.resolve(reference), self.is_collective(reference)
        return self._find_descriptive_candidates(normalized_text)

    def _add_name(self, name, entity_id):
        if entity_id in self._ids:
            self._names.setdefault(self._norm(name), set()).add(entity_id)

    def _collectives(self, values):
        return {
            self._norm(name): frozenset(entity_ids) & self._ids
            for name, entity_ids in values.items()
        }

    def _find_descriptive_candidates(self, text):
        words = set(text.replace("?", " ").replace(".", " ").split())
        domain_words = {
            "light": "light", "lights": "light",
            "switch": "switch", "switches": "switch",
            "sensor": "sensor", "sensors": "sensor",
            "cover": "cover", "covers": "cover",
            "camera": "camera", "cameras": "camera",
            "button": "button", "buttons": "button",
            "fan": "fan", "fans": "fan",
            "lock": "lock", "locks": "lock",
        }
        domain = next((value for word, value in domain_words.items() if word in words), None)
        ignored = {
            "what", "which", "is", "are", "the", "a", "an", "of", "in", "at",
            "my", "status", "state", "on", "off", "all", "device", "devices",
            *domain_words,
        }
        topic = words - ignored
        if not topic:
            return None
        candidates = set()
        for name in self._descriptive_names:
            if topic <= set(name.split()):
                candidates.update(self.resolve(name, domain))
        if not candidates:
            return None
        return " ".join(sorted(topic)), tuple(sorted(candidates)), False

    @staticmethod
    def _norm(value):
        return " ".join(str(value).casefold().split())

    @staticmethod
    def _contains_reference(text, reference):
        padded = f" {text} "
        return (
            f" {reference} " in padded
            or f" {reference}?" in padded
            or f" {reference}." in padded
        )
