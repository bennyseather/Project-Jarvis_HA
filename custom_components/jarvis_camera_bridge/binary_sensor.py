"""Bridge availability entities."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [BridgeOnline(coordinator)]
    entities.extend(StreamConnected(coordinator, camera) for camera in coordinator.data["cameras"])
    async_add_entities(entities)


class BridgeOnline(CoordinatorEntity, BinarySensorEntity):
    _attr_name = "Jarvis Camera Bridge"
    _attr_unique_id = "jarvis_camera_bridge_online"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    @property
    def is_on(self):
        return self.coordinator.last_update_success and bool((self.coordinator.data or {}).get("online"))


class StreamConnected(CoordinatorEntity, BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Stream connected"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator, camera):
        super().__init__(coordinator)
        self.camera_id = camera["id"]
        self._attr_unique_id = f"jarvis_camera_{self.camera_id}_connected"
        self._attr_device_info = {"identifiers": {(DOMAIN, self.camera_id)}}

    @property
    def is_on(self):
        return bool(self.coordinator.camera(self.camera_id).get("connected"))
