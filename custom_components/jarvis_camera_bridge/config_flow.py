"""Configuration flow."""

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import BridgeApi
from .const import CONF_TOKEN, CONF_URL, DEFAULT_URL, DOMAIN


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                status = await BridgeApi(
                    async_get_clientsession(self.hass), user_input[CONF_URL], user_input[CONF_TOKEN]
                ).status()
                if not status.get("cameras"):
                    errors["base"] = "no_cameras"
                else:
                    await self.async_set_unique_id("project_jarvis_camera_bridge")
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(title="Project Jarvis Camera Bridge", data=user_input)
            except Exception:
                errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_URL, default=DEFAULT_URL): str,
                    vol.Required(CONF_TOKEN): str,
                }
            ),
            errors=errors,
        )
