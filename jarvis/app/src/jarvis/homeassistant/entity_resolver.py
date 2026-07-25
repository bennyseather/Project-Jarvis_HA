"""
Resolve Home Assistant entities from user-friendly names.
"""

from jarvis.homeassistant.entity_registry import EntityRegistry
from jarvis.models.entity import Entity


class EntityResolver:
    """
    Resolves Home Assistant entities from human-friendly names.
    """

    def __init__(self, registry: EntityRegistry):
        """
        Create a new entity resolver.
        """
        self.registry = registry

    def resolve(
        self,
        target: str,
        domain: str | None = None,
    ) -> Entity | None:
        """
        Resolve a target name into a Home Assistant entity.

        If a domain is supplied, only entities from that
        Home Assistant domain are considered.

        Returns:
            Entity if a unique match is found.
            None otherwise.
        """

        if not target:
            return None

        target = target.lower().strip()

        matches = [
            entity
            for entity in self.registry.all()
            if target in entity.entity_id.lower()
        ]

        if domain is not None:
            domain = domain.lower().strip()

            matches = [
                entity
                for entity in matches
                if entity.entity_id.lower().startswith(f"{domain}.")
            ]

        if len(matches) == 1:
            return matches[0]

        return None