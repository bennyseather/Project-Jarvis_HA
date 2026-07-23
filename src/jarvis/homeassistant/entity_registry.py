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

    def count(self) -> int:
        """
        Return the number of loaded entities.
        """

        return len(self.entities)