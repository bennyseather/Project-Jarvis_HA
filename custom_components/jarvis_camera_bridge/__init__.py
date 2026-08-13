"""Project Jarvis Camera Bridge integration."""

from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import BridgeApi
from .const import CONF_TOKEN, CONF_URL, DOMAIN, PLATFORMS
from .coordinator import BridgeCoordinator


async def async_setup_entry(hass, entry):
    api = BridgeApi(async_get_clientsession(hass), entry.data[CONF_URL], entry.data[CONF_TOKEN])
    coordinator = BridgeCoordinator(hass, api)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass, entry):
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unloaded
