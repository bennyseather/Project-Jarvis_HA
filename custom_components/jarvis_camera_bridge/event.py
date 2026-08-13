"""Doorbell-event foundation. No notification or speech is emitted here."""

from homeassistant.components.event import EventEntity
from homeassistant.core import Event, callback
from homeassistant.helpers.storage import Store

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([JarvisDoorbellEvent(hass, entry.entry_id)])


class JarvisDoorbellEvent(EventEntity):
    _attr_name = "Jarvis Doorbell"
    _attr_unique_id = "jarvis_doorbell_event"
    _attr_event_types = ["doorbell"]
    _attr_icon = "mdi:doorbell-video"

    def __init__(self, hass, entry_id):
        self.hass = hass
        self.store = Store(hass, 1, f"{DOMAIN}.{entry_id}.doorbell_events")
        self.history = []
        self._remove_listener = None

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        saved = await self.store.async_load()
        self.history = saved if isinstance(saved, list) else []
        self._remove_listener = self.hass.bus.async_listen("state_changed", self._state_changed)

    async def async_will_remove_from_hass(self):
        if self._remove_listener:
            self._remove_listener()

    @callback
    def _state_changed(self, event: Event):
        entity_id = event.data.get("entity_id", "")
        state = event.data.get("new_state")
        if not state or not entity_id.startswith("event.") or entity_id == self.entity_id:
            return
        attrs = state.attributes
        event_type = str(attrs.get("event_type", "")).lower()
        if not (
            attrs.get("device_class") == "doorbell"
            or "doorbell" in entity_id
            or event_type in {"doorbell", "chime", "ring"}
        ):
            return
        record = {
            "source_entity_id": entity_id,
            "occurred_at": state.last_changed.isoformat(),
            "event_type": event_type or "doorbell",
            "thumbnail": attrs.get("thumbnail") or attrs.get("entity_picture"),
        }
        self.history = (self.history + [record])[-20:]
        self._trigger_event("doorbell", record)
        self.hass.async_create_task(self.store.async_save(self.history))

    @property
    def extra_state_attributes(self):
        return {
            "last_event": self.history[-1] if self.history else None,
            "recorded_events": len(self.history),
            "voice_notifications_enabled": False,
        }
