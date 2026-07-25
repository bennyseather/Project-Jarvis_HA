"""Read-only adapter for Home Assistant current entity state."""
from __future__ import annotations
from jarvis.models.assistant_slice import HomeAssistantState
class HomeAssistantReadAdapter:
    def __init__(self, client) -> None: self._client=client
    async def read_entity_state(self, entity_id: str) -> HomeAssistantState:
        for entity in await self._client.get_states():
            if entity.get("entity_id")==entity_id:
                return HomeAssistantState(entity_id,str(entity.get("state","unknown")),dict(entity.get("attributes",{})))
        raise LookupError(f"Home Assistant entity unavailable: {entity_id}")
