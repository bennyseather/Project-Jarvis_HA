"""Cached Jarvis camera entities."""

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(JarvisBridgeCamera(coordinator, item) for item in coordinator.data["cameras"])


class JarvisBridgeCamera(CoordinatorEntity, Camera):
    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = CameraEntityFeature.STREAM

    def __init__(self, coordinator, camera):
        Camera.__init__(self)
        CoordinatorEntity.__init__(self, coordinator)
        self.camera_id = camera["id"]
        self._attr_unique_id = f"jarvis_camera_{self.camera_id}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, self.camera_id)},
            "name": f"Jarvis {camera['name']}",
            "manufacturer": "Project Jarvis",
            "model": "Cached Nest Camera Bridge",
        }

    @property
    def available(self):
        camera = self.coordinator.camera(self.camera_id)
        return (
            self.coordinator.last_update_success
            and camera.get("snapshot_available", False)
            and not camera.get("snapshot_stale", True)
        )

    @property
    def extra_state_attributes(self):
        camera = self.coordinator.camera(self.camera_id)
        return {
            "jarvis_bridge": True,
            "bridge_available": bool((self.coordinator.data or {}).get("online")),
            "stream_connected": camera.get("connected", False),
            "snapshot_age_seconds": camera.get("snapshot_age_seconds"),
            "snapshot_stale": camera.get("snapshot_stale", True),
            "last_successful_frame": camera.get("last_success"),
            "last_bridge_error": camera.get("last_error", ""),
            "cooldown_seconds": camera.get("cooldown_seconds", 0),
            "active_viewers": camera.get("active_viewers", 0),
        }

    async def async_camera_image(self, width=None, height=None):
        return await self.coordinator.api.snapshot(self.camera_id)

    async def stream_source(self):
        return self.coordinator.api.rtsp_url(self.camera_id)
