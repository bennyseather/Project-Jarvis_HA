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
    await coordinator.async_config_entry_first_refresh()
    async_add_entities([JarvisLearningInsightsSensor(coordinator, entry)])


class JarvisLearningInsightsSensor(CoordinatorEntity, SensorEntity):
    _attr_name = "Jarvis Learning Insights"
    _attr_icon = "mdi:brain"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_learning_insights"

    @property
    def native_value(self):
        return self.coordinator.data.get("state", 0)

    @property
    def extra_state_attributes(self):
        return dict(self.coordinator.data)
