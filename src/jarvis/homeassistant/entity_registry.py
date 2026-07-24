"""
Stores Home Assistant entities in memory.
"""

from jarvis.models.entity import Entity


class EntityRegistry:
    """
    Stores and manages Home Assistant entities.
    """

    def __init__(self):
        self.entities = {}

    def load(self, raw_entities: list):
        """
        Load entities from Home Assistant.
        """

        self.entities.clear()

        for raw_entity in raw_entities:
            entity = Entity(raw_entity)
            self.entities[entity.entity_id] = entity

    def get(self, entity_id: str):
        """
        Retrieve an entity by its entity ID.
        """

        return self.entities.get(entity_id)

    def find(self, name: str):
        """
        Find an entity by a partial entity ID.

        Returns the matching Entity if exactly one match is found.
        Returns None if no match or multiple matches are found.
        """

        name = name.lower().strip()

        matches = [
            entity
            for entity in self.entities.values()
            if name in entity.entity_id.lower()
        ]

        print()
        print(f"Searching for: {name}")
        print(f"Matches found: {len(matches)}")

        for entity in matches:
            print(f" - {entity.entity_id}")

        if len(matches) == 1:
            return matches[0]

        return None

    def all(self) -> list[Entity]:
        """
        Return all loaded entities.
        """

        return list(self.entities.values())

    def count(self) -> int:
        """
        Return the number of loaded entities.
        """

        return len(self.entities)