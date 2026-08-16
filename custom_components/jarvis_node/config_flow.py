import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import JarvisNodeApi
from .const import CONF_TOKEN, CONF_URL, DEFAULT_URL, DOMAIN


class JarvisNodeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input:
            try:
                payload = await JarvisNodeApi(
                    async_get_clientsession(self.hass), user_input[CONF_URL], user_input[CONF_TOKEN]
                ).status()
                await self.async_set_unique_id(payload.get("node", "jarvis-node"))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Jarvis AI Node", data=user_input)
            except (ConnectionError, TimeoutError, ValueError):
                errors["base"] = "cannot_connect"
        schema = vol.Schema({vol.Required(CONF_URL, default=DEFAULT_URL): str, vol.Required(CONF_TOKEN): str})
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
