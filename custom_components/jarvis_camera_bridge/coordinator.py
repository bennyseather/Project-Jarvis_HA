"""Shared status coordinator."""

from datetime import timedelta

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN


class BridgeCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, api) -> None:
        super().__init__(hass, logger=__import__("logging").getLogger(__name__), name=DOMAIN, update_interval=timedelta(seconds=10))
        self.api = api

    async def _async_update_data(self):
        try:
            return await self.api.status()
        except Exception as err:
            raise UpdateFailed(f"Camera bridge unavailable: {err}") from err

    def camera(self, camera_id: str) -> dict:
        return next((item for item in (self.data or {}).get("cameras", []) if item["id"] == camera_id), {})
