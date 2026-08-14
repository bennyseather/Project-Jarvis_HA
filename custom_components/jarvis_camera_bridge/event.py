"""Doorbell-event foundation. No notification or speech is emitted here."""

from homeassistant.components.event import EventEntity
from homeassistant.core import Event, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([JarvisDoorbellEvent(hass, entry.entry_id, coordinator)])


class JarvisDoorbellEvent(EventEntity):
    _attr_name = "Jarvis Doorbell"
    _attr_unique_id = "jarvis_doorbell_event"
    _attr_event_types = ["doorbell"]
    _attr_icon = "mdi:doorbell-video"

    def __init__(self, hass, entry_id, coordinator):
        self.hass = hass
        self.coordinator = coordinator
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
        camera = self._event_camera(entity_id)
        if not camera:
            return
        record = {
            "source_entity_id": entity_id,
            "occurred_at": state.last_changed.isoformat(),
            "event_type": event_type or "doorbell",
            "thumbnail": attrs.get("thumbnail") or attrs.get("entity_picture"),
            "camera_id": camera["id"],
            "camera_name": camera.get("name", "Front Door"),
        }
        self.hass.async_create_task(self._activate_and_publish(camera, record))

    def _event_camera(self, source_entity_id: str):
        event_cameras = [
            item for item in (self.coordinator.data or {}).get("cameras", [])
            if item.get("mode") == "event_driven"
        ]
        exact = next((item for item in event_cameras if item.get("trigger_entity") == source_entity_id), None)
        if exact:
            return exact
        unbound = [item for item in event_cameras if not item.get("trigger_entity")]
        return unbound[0] if len(unbound) == 1 else None

    async def _activate_and_publish(self, camera: dict, record: dict):
        try:
            activation = await self.coordinator.api.activate(camera["id"])
            await self.coordinator.async_request_refresh()
        except Exception as err:
            record["activation_error"] = type(err).__name__
            self.history = (self.history + [record])[-20:]
            self._trigger_event("doorbell", record)
            self.async_write_ha_state()
            await self.store.async_save(self.history)
            return
        registry = er.async_get(self.hass)
        camera_entity_id = registry.async_get_entity_id(
            "camera", DOMAIN, f"jarvis_camera_{camera['id']}"
        )
        record.update(
            {
                "camera_entity_id": camera_entity_id,
                "session_seconds": activation.get("session_seconds", 45),
                "voice_notifications_enabled": False,
                "push_notifications_enabled": False,
            }
        )
        self.history = (self.history + [record])[-20:]
        self._trigger_event("doorbell", record)
        self.async_write_ha_state()
        self.hass.bus.async_fire("jarvis_camera_bridge_doorbell", record)
        await self.store.async_save(self.history)

    @property
    def extra_state_attributes(self):
        return {
            "last_event": self.history[-1] if self.history else None,
            "recorded_events": len(self.history),
            "voice_notifications_enabled": False,
            "push_notifications_enabled": False,
        }
