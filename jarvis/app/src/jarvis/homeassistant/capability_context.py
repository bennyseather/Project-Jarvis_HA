"""Build bounded model context from discovered and authorized capabilities."""
from __future__ import annotations


class HomeAssistantCapabilityContext:
    def __init__(self, catalog, allowed_read_entities=(), allowed_action_entities=(), allowed_services=(), aliases=None, maximum_items=50):
        if not isinstance(maximum_items, int) or not 1 <= maximum_items <= 100:
            raise ValueError("maximum_items must be between 1 and 100")
        known = catalog.entity_ids
        self._reads = tuple(sorted(set(allowed_read_entities) & known))[:maximum_items]
        self._actions = tuple(sorted(set(allowed_action_entities) & known))[:maximum_items]
        permitted_services = set(allowed_services)
        self._services = tuple(
            {"domain": service.domain, "service": service.service, "fields": tuple(sorted(service.fields))}
            for service in catalog.services
            if f"{service.domain}.{service.service}" in permitted_services or f"{service.domain}.*" in permitted_services
        )[:maximum_items]
        aliases = aliases or {}
        permitted_entities = set(self._reads) | set(self._actions)
        self._aliases = {alias: entity for alias, entity in aliases.items() if entity in permitted_entities}

    def as_context(self) -> dict[str, object]:
        return {"read_entities": self._reads, "action_entities": self._actions, "aliases": dict(self._aliases), "services": self._services}
