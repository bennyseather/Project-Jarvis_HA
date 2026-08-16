from datetime import timedelta

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN


class JarvisNodeCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, api):
        super().__init__(hass, logger=__import__("logging").getLogger(__name__), name=DOMAIN, update_interval=timedelta(seconds=15))
        self.api = api

    async def _async_update_data(self):
        try:
            return await self.api.status()
        except (ConnectionError, TimeoutError) as err:
            raise UpdateFailed(str(err)) from err
