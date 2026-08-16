from datetime import datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import PERCENTAGE, UnitOfPower, UnitOfTemperature, UnitOfTime

from .const import DOMAIN
from .entity import JarvisNodeEntity, nested


FIELDS = {
    "cpu_usage": ("CPU usage", "cpu.usage_percent", PERCENTAGE, "mdi:cpu-64-bit", None),
    "cpu_temperature": ("CPU temperature", "cpu.temperature_c", UnitOfTemperature.CELSIUS, "mdi:thermometer", SensorDeviceClass.TEMPERATURE),
    "load_1m": ("CPU load 1 minute", "cpu.load_1m", None, "mdi:gauge", None),
    "memory_usage": ("Memory usage", "memory.usage_percent", PERCENTAGE, "mdi:memory", None),
    "memory_used": ("Memory used", "memory.used_gib", "GiB", "mdi:memory", SensorDeviceClass.DATA_SIZE),
    "memory_available": ("Memory available", "memory.available_gib", "GiB", "mdi:memory", SensorDeviceClass.DATA_SIZE),
    "swap_used": ("Swap used", "memory.swap_used_gib", "GiB", "mdi:swap-horizontal", SensorDeviceClass.DATA_SIZE),
    "disk_usage": ("NVMe usage", "disk.usage_percent", PERCENTAGE, "mdi:harddisk", None),
    "disk_free": ("NVMe free", "disk.free_gib", "GiB", "mdi:harddisk", SensorDeviceClass.DATA_SIZE),
    "disk_temperature": ("NVMe temperature", "disk.temperature_c", UnitOfTemperature.CELSIUS, "mdi:thermometer", SensorDeviceClass.TEMPERATURE),
    "uptime": ("Uptime", "uptime_seconds", UnitOfTime.SECONDS, "mdi:timer-outline", SensorDeviceClass.DURATION),
    "last_update": ("Last update", "timestamp", None, "mdi:clock-check-outline", SensorDeviceClass.TIMESTAMP),
}


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [JarvisNodeSensor(coordinator, key, *details) for key, details in FIELDS.items()]
    for gpu in coordinator.data.get("gpus", []):
        entities.extend(JarvisGpuSensor(coordinator, gpu["uuid"], key) for key in ("utilization_percent", "temperature_c", "memory_usage_percent", "memory_used_mib", "power_w"))
    async_add_entities(entities)


class JarvisNodeSensor(JarvisNodeEntity, SensorEntity):
    def __init__(self, coordinator, unique, name, path, unit, icon, device_class):
        super().__init__(coordinator, unique)
        self.path = path
        self._attr_name, self._attr_native_unit_of_measurement = name, unit
        self._attr_icon, self._attr_device_class = icon, device_class
        if path != "timestamp":
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        value = nested(self.coordinator.data, self.path)
        return datetime.fromisoformat(value) if self.path == "timestamp" and value else value


GPU_FIELDS = {
    "utilization_percent": ("GPU usage", PERCENTAGE, "mdi:expansion-card", None),
    "temperature_c": ("GPU temperature", UnitOfTemperature.CELSIUS, "mdi:thermometer", SensorDeviceClass.TEMPERATURE),
    "memory_usage_percent": ("GPU memory usage", PERCENTAGE, "mdi:memory", None),
    "memory_used_mib": ("GPU memory used", "MiB", "mdi:memory", SensorDeviceClass.DATA_SIZE),
    "power_w": ("GPU power", UnitOfPower.WATT, "mdi:lightning-bolt", SensorDeviceClass.POWER),
}


class JarvisGpuSensor(JarvisNodeEntity, SensorEntity):
    def __init__(self, coordinator, uuid, field):
        super().__init__(coordinator, f"{uuid}_{field}")
        self.uuid, self.field = uuid, field
        name, unit, icon, device_class = GPU_FIELDS[field]
        gpu = next(item for item in coordinator.data["gpus"] if item["uuid"] == uuid)
        self._attr_name = f"{gpu['name']} {name}"
        self._attr_native_unit_of_measurement, self._attr_icon = unit, icon
        self._attr_device_class, self._attr_state_class = device_class, SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        gpu = next((item for item in self.coordinator.data.get("gpus", []) if item["uuid"] == self.uuid), {})
        return gpu.get(self.field)
