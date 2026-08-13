"""Camera bridge diagnostic sensors."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


FIELDS = {
    "snapshot_age_seconds": ("Snapshot age", "s", "mdi:timer-outline"),
    "last_error": ("Last Nest error", None, "mdi:alert-circle-outline"),
    "cooldown_seconds": ("Reconnect cooldown", "s", "mdi:timer-sand"),
    "active_viewers": ("Active viewers", None, "mdi:eye-outline"),
}


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        BridgeDiagnostic(coordinator, camera, key, details)
        for camera in coordinator.data["cameras"]
        for key, details in FIELDS.items()
    )


class BridgeDiagnostic(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, camera, key, details):
        super().__init__(coordinator)
        self.camera_id, self.key = camera["id"], key
        self._attr_name, self._attr_native_unit_of_measurement, self._attr_icon = details
        self._attr_unique_id = f"jarvis_camera_{self.camera_id}_{key}"
        self._attr_device_info = {"identifiers": {(DOMAIN, self.camera_id)}}

    @property
    def native_value(self):
        value = self.coordinator.camera(self.camera_id).get(self.key)
        if self.key == "last_error":
            return value if value else "None"
        return value
