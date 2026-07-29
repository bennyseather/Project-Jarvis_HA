"""Deterministic, authorization-bounded Home Assistant reference resolution."""
from __future__ import annotations


class EntityReferenceResolver:
    """Resolve exact entities and explicitly named collectives without guessing."""

    _DOMAIN_WORDS = {
        "light": "light", "lights": "light",
        "switch": "switch", "switches": "switch",
        "sensor": "sensor", "sensors": "sensor",
        "cover": "cover", "covers": "cover",
        "camera": "camera", "cameras": "camera",
        "button": "button", "buttons": "button",
        "fan": "fan", "fans": "fan",
        "lock": "lock", "locks": "lock",
    }

    def __init__(
        self,
        allowed_entity_ids,
        aliases=None,
        friendly_names=None,
        areas=None,
        groups=None,
        floors=None,
    ):
        self._ids = frozenset(allowed_entity_ids)
        self._areas = self._collectives(areas or {})
        self._groups = self._collectives(groups or {})
        self._floors = self._collectives(floors or {})
        self._group_entity_ids = frozenset(
            name for name in self._groups if name in self._ids and "." in name
        )
        self._names: dict[str, set[str]] = {}
        self._descriptive_names: set[str] = set()
        self._labels: dict[str, str] = {}

        for entity_id in self._ids:
            self._add_name(entity_id, entity_id)
            self._add_name(entity_id.replace(".", " ").replace("_", " "), entity_id)
        for name, entity_id in (aliases or {}).items():
            self._add_name(name, entity_id)
            self._descriptive_names.add(self._norm(name))
            if entity_id in self._ids:
                self._labels.setdefault(entity_id, str(name))
        for name, targets in (friendly_names or {}).items():
            self._descriptive_names.add(self._norm(name))
            if isinstance(targets, str):
                targets = (targets,)
            for entity_id in targets:
                self._add_name(name, entity_id)
                if entity_id in self._ids:
                    self._labels[entity_id] = str(name)

    def resolve(self, reference, domain: str | None = None):
        normalized = self._norm(reference)
        spatial_reference = normalized in self._areas or normalized in self._floors
        matches = (
            self._areas.get(normalized)
            or self._groups.get(normalized)
            or self._floors.get(normalized)
        )
        if matches is None:
            matches = self._names.get(normalized, ())
        return tuple(sorted(
            entity_id for entity_id in matches
            if entity_id in self._ids
            and (domain is None or entity_id.partition(".")[0] == domain)
            and not (
                spatial_reference
                and domain is not None
                and entity_id in self._group_entity_ids
            )
        ))

    def is_collective(self, reference) -> bool:
        normalized = self._norm(reference)
        return (
            normalized in self._areas
            or normalized in self._groups
            or normalized in self._floors
        )

    def candidates(self, reference, limit: int = 5):
        return self.resolve(reference)[:limit]

    def display_name(self, entity_id):
        """Return Home Assistant's friendly name, falling back to the entity ID."""
        return self._labels.get(entity_id, entity_id)

    def infer_domain(self, text):
        """Return an explicitly named Home Assistant device domain."""
        words = set(self._norm(text).replace("?", " ").replace(".", " ").split())
        return next(
            (domain for word, domain in self._DOMAIN_WORDS.items() if word in words),
            None,
        )

    def find_in_text(self, text):
        """Return the longest configured reference explicitly present in text."""
        normalized_text = self._norm(text)
        references = (
            set(self._areas)
            | set(self._groups)
            | set(self._floors)
            | set(self._names)
        )
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
        domain = self.infer_domain(text)
        ignored = {
            "what", "which", "is", "are", "the", "a", "an", "of", "in", "at",
            "my", "status", "state", "on", "off", "all", "device", "devices",
            *self._DOMAIN_WORDS,
        }
        topic = words - ignored
        if not topic:
            return None
        collective_matches = []
        for name in set(self._areas) | set(self._groups) | set(self._floors):
            targets = self.resolve(name, domain)
            if topic <= set(name.split()) and targets:
                collective_matches.append((name, targets))
        if len(collective_matches) == 1:
            name, targets = collective_matches[0]
            return name, targets, True
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
