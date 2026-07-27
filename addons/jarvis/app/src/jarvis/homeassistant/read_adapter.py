"""Read-only adapter for Home Assistant current entity state."""
from __future__ import annotations
from jarvis.models.assistant_slice import HomeAssistantState
class HomeAssistantReadAdapter:
    def __init__(self, client) -> None: self._client=client
    async def read_entity_state(self, entity_id: str) -> HomeAssistantState:
        states = await self.read_entity_states((entity_id,))
        if states:
            return states[0]
        raise LookupError(f"Home Assistant entity unavailable: {entity_id}")
    async def read_entity_states(self, entity_ids) -> tuple[HomeAssistantState, ...]:
        requested = frozenset(entity_ids)
        states = {
            entity["entity_id"]: HomeAssistantState(
                entity["entity_id"], str(entity.get("state", "unknown")),
                dict(entity.get("attributes", {})),
            )
            for entity in await self._client.get_states()
            if entity.get("entity_id") in requested
        }
        return tuple(states[entity_id] for entity_id in entity_ids if entity_id in states)
