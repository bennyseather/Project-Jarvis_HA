"""Project Jarvis learning-insights sensor."""
from __future__ import annotations

from datetime import timedelta
import logging
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, CoordinatorEntity


async def async_setup_entry(hass, entry, async_add_entities):
    session = async_get_clientsession(hass)

    async def update():
        async with session.get(
            entry.data["bridge_url"] + "/v1/learning",
            headers={"Authorization": "Bearer " + entry.data["api_key"]},
            timeout=15,
        ) as response:
            response.raise_for_status()
            return await response.json()

    coordinator = DataUpdateCoordinator(
        hass, logger=logging.getLogger(__name__),
        name="Project Jarvis learning insights", update_method=update,
        update_interval=timedelta(minutes=2),
    )
    async def update_orchestration():
        async with session.get(
            entry.data["bridge_url"] + "/v1/orchestration",
            headers={"Authorization": "Bearer " + entry.data["api_key"]},
            timeout=15,
        ) as response:
            response.raise_for_status()
            return await response.json()

    orchestration = DataUpdateCoordinator(
        hass, logger=logging.getLogger(__name__),
        name="Project Jarvis orchestration performance",
        update_method=update_orchestration, update_interval=timedelta(seconds=30),
    )
    async_add_entities([
        JarvisLearningInsightsSensor(coordinator, entry),
        JarvisOrchestrationSensor(orchestration, entry, "p95_ms", "P95 Latency", "ms", "mdi:speedometer"),
        JarvisOrchestrationSensor(orchestration, entry, "p50_ms", "Median Latency", "ms", "mdi:timer-outline"),
        JarvisOrchestrationSensor(orchestration, entry, "success_percent", "Success Rate", "%", "mdi:check-decagram"),
        JarvisOrchestrationSensor(orchestration, entry, "cache_hit_percent", "Cache Hit Rate", "%", "mdi:cached"),
    ])
    await coordinator.async_refresh()
    await orchestration.async_refresh()


class JarvisLearningInsightsSensor(CoordinatorEntity, SensorEntity):
    _attr_name = "Jarvis Learning Insights"
    _attr_icon = "mdi:brain"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_learning_insights"

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get("state", 0)

    @property
    def extra_state_attributes(self):
        return dict(self.coordinator.data or {})


class JarvisOrchestrationSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, entry, key, label, unit, icon):
        super().__init__(coordinator)
        self._key = key
        self._attr_name = f"Jarvis {label}"
        self._attr_unique_id = f"{entry.entry_id}_orchestration_{key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get(self._key, 0)

    @property
    def extra_state_attributes(self):
        return dict(self.coordinator.data or {})
