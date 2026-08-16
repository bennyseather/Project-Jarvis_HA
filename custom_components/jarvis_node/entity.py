from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


class JarvisNodeEntity(CoordinatorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, unique: str):
        super().__init__(coordinator)
        self._attr_unique_id = f"jarvis_node_{unique}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, "jarvis-node")},
            "name": "Jarvis AI Node",
            "manufacturer": "Project Jarvis",
            "model": "Dedicated dual-GPU AI node",
        }


def nested(data, path):
    for part in path.split("."):
        data = data.get(part, {}) if isinstance(data, dict) else None
    return data
