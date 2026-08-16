from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity

from .const import DOMAIN
from .entity import JarvisNodeEntity, nested


FIELDS = {
    "healthy": ("System health", "healthy", BinarySensorDeviceClass.PROBLEM, True),
    "qwen": ("Qwen voice", "services.qwen", BinarySensorDeviceClass.CONNECTIVITY, False),
    "ollama": ("Ollama", "services.ollama", BinarySensorDeviceClass.CONNECTIVITY, False),
    "nvme": ("NVMe health", "disk.healthy", BinarySensorDeviceClass.PROBLEM, True),
}


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(JarvisNodeBinary(coordinator, key, *details) for key, details in FIELDS.items())


class JarvisNodeBinary(JarvisNodeEntity, BinarySensorEntity):
    def __init__(self, coordinator, unique, name, path, device_class, invert):
        super().__init__(coordinator, unique)
        self.path, self.invert = path, invert
        self._attr_name, self._attr_device_class = name, device_class

    @property
    def is_on(self):
        value = bool(nested(self.coordinator.data, self.path))
        return not value if self.invert else value
