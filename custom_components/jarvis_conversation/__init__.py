"""Project Jarvis custom integration."""
from homeassistant.const import Platform

async def async_setup_entry(hass, entry):
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.CONVERSATION, Platform.SENSOR])
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True

async def async_unload_entry(hass, entry):
    return await hass.config_entries.async_unload_platforms(entry, [Platform.CONVERSATION, Platform.SENSOR])


async def async_migrate_entry(hass, entry):
    """Advance existing bridge-only entries to the voice-capable schema."""
    if entry.version < 3:
        hass.config_entries.async_update_entry(entry, version=3)
    return True


async def _async_update_listener(hass, entry):
    """Reload Jarvis when its voice-routing options change."""
    await hass.config_entries.async_reload(entry.entry_id)
