"""Project Jarvis custom integration."""
from homeassistant.const import Platform

async def async_setup_entry(hass, entry):
    from homeassistant.components import websocket_api
    from .listening import listen
    from .household import household
    from .planner import planner
    from .calendar_manage import calendar_manage
    from homeassistant.components.frontend import add_extra_js_url, remove_extra_js_url
    planner_url = '/local/jarvis/jarvis-household.js?v=04587'
    add_extra_js_url(hass, planner_url)
    entry.async_on_unload(lambda: remove_extra_js_url(hass, planner_url))
    websocket_api.async_register_command(hass, listen)
    websocket_api.async_register_command(hass, household)
    websocket_api.async_register_command(hass, planner)
    websocket_api.async_register_command(hass, calendar_manage)
    from .speaker_bridge import register as register_speaker
    await register_speaker(hass)
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.CONVERSATION, Platform.SENSOR])
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True

async def async_unload_entry(hass, entry):
    unloaded = await hass.config_entries.async_unload_platforms(entry, [Platform.CONVERSATION, Platform.SENSOR])
    if unloaded:
        domain = hass.data.get('jarvis_conversation', {})
        bridge = domain.pop('speaker_bridge', None)
        domain.pop('speaker_capture_factory', None)
        if bridge:
            await bridge.close()
    return unloaded


async def async_migrate_entry(hass, entry):
    """Advance existing bridge-only entries to the voice-capable schema."""
    if entry.version < 3:
        hass.config_entries.async_update_entry(entry, version=3)
    return True


async def _async_update_listener(hass, entry):
    """Reload Jarvis when its voice-routing options change."""
    await hass.config_entries.async_reload(entry.entry_id)
