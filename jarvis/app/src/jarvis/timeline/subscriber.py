"""Dedicated read-only Home Assistant event subscriber."""
from __future__ import annotations
from datetime import datetime, timezone


class HomeAssistantEventSubscriber:
    def __init__(self, client, policy, store, observers=()):
        self._client, self._policy, self._store = client, policy, store
        self._observers = tuple(observers)

    async def run(self) -> None:
        await self._client.connect()
        for event_type in self._policy._types:
            await self._subscribe(event_type)
        while True:
            message = await self._client.receive_json()
            self.process(message)

    async def _subscribe(self, event_type: str) -> None:
        await self._client.send_json({
            "id": self._client.get_next_message_id(),
            "type": "subscribe_events",
            "event_type": event_type,
        })
        response = await self._client.receive_json()
        if response.get("type") != "result" or not response.get("success", False):
            raise RuntimeError("Home Assistant event subscription failed")

    def process(self, message: dict) -> None:
        if message.get("type") != "event":
            return
        event = message.get("event", {})
        data = event.get("data", {})
        event_type, entity_id = event.get("event_type"), data.get("entity_id")
        if not isinstance(event_type, str) or not isinstance(entity_id, str) or not self._policy.permits(event_type, entity_id):
            return
        new_state = data.get("new_state") if isinstance(data.get("new_state"), dict) else {}
        state = new_state.get("state") if isinstance(new_state.get("state"), str) else None
        old_state_value = data.get("old_state") if isinstance(data.get("old_state"), dict) else {}
        old_state = old_state_value.get("state") if isinstance(old_state_value.get("state"), str) else None
        occurred_at = datetime.fromisoformat(event["time_fired"].replace("Z", "+00:00")) if isinstance(event.get("time_fired"), str) else datetime.now(timezone.utc)
        self._store.append(event_type, entity_id, occurred_at, state)
        for observer in self._observers:
            try:
                observer(event_type, entity_id, occurred_at, state, old_state)
            except Exception:
                # Optional analysis must never interrupt the durable HA timeline.
                continue
