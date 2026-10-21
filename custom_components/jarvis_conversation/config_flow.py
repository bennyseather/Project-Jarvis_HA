"""Configuration flow for Project Jarvis Conversation."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import aiohttp
import voluptuous as vol

from .const import (
    CONF_EXTERNAL_VOICE_OUTPUT,
    CONF_INPUT_DEVICE_ID,
    CONF_OUTPUT_MEDIA_PLAYER,
    CONF_PROACTIVE_VOICE_OUTPUT,
    CONF_SUPPRESS_LOCAL_AUDIO,
    CONF_TTS_ENTITY,
    CONF_TTS_LANGUAGE,
    CONF_TTS_VOICE,
    DEFAULT_TTS_LANGUAGE,
    DOMAIN,
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 3

    async def async_step_reconfigure(self, user_input=None):
        """Rotate credentials using HA's supported flow, never raw storage edits.

        The destination is the existing trusted entry, not user-supplied input.
        Never echo a credential in errors, defaults or logging.
        """
        entry = self._get_reconfigure_entry()
        errors = {}
        if user_input is not None:
            key = user_input.get('api_key', '')
            if not isinstance(key, str) or not 32 <= len(key) <= 512 or any(c.isspace() for c in key):
                errors['base'] = 'invalid_auth'
            else:
                try:
                    session = async_get_clientsession(self.hass)
                    async with session.get(
                        entry.data['bridge_url'].rstrip('/') + '/v1/household',
                        headers={'Authorization': 'Bearer ' + key},
                        timeout=aiohttp.ClientTimeout(total=10),
                        allow_redirects=False,
                    ) as response:
                        if response.status != 200:
                            errors['base'] = 'invalid_auth' if response.status in (401, 403) else 'cannot_connect'
                except (aiohttp.ClientError, TimeoutError):
                    errors['base'] = 'cannot_connect'
                if not errors:
                    return self.async_update_reload_and_abort(entry, data_updates={'api_key': key})
        return self.async_show_form(
            step_id='reconfigure', errors=errors,
            data_schema=vol.Schema({vol.Required('api_key'): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD))}),
        )

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="Project Jarvis", data=user_input)
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "bridge_url", default="http://local-jarvis:8099"
                    ): str,
                    vol.Required("api_key"): str,
                }
            ),
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        return JarvisOptionsFlow()


class JarvisOptionsFlow(config_entries.OptionsFlow):
    """Configure Home Assistant-owned external TTS routing."""

    async def async_step_init(self, user_input=None):
        errors = {}
        if user_input is not None:
            if user_input[CONF_EXTERNAL_VOICE_OUTPUT]:
                if self.hass.states.get(user_input[CONF_OUTPUT_MEDIA_PLAYER]) is None:
                    errors[CONF_OUTPUT_MEDIA_PLAYER] = "entity_not_found"
                if self.hass.states.get(user_input[CONF_TTS_ENTITY]) is None:
                    errors[CONF_TTS_ENTITY] = "entity_not_found"
                if not self.hass.services.has_service("tts", "speak"):
                    errors["base"] = "tts_speak_unavailable"
            if not errors:
                return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_EXTERNAL_VOICE_OUTPUT,
                    default=current.get(CONF_EXTERNAL_VOICE_OUTPUT, False),
                ): selector.BooleanSelector(),
                vol.Required(
                    CONF_INPUT_DEVICE_ID,
                    default=current.get(CONF_INPUT_DEVICE_ID, vol.UNDEFINED),
                ): selector.DeviceSelector(),
                vol.Required(
                    CONF_OUTPUT_MEDIA_PLAYER,
                    default=current.get(CONF_OUTPUT_MEDIA_PLAYER, vol.UNDEFINED),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="media_player")
                ),
                vol.Required(
                    CONF_TTS_ENTITY,
                    default=current.get(CONF_TTS_ENTITY, vol.UNDEFINED),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="tts")
                ),
                vol.Optional(
                    CONF_TTS_LANGUAGE,
                    default=current.get(CONF_TTS_LANGUAGE, DEFAULT_TTS_LANGUAGE),
                ): selector.TextSelector(),
                vol.Optional(
                    CONF_TTS_VOICE,
                    default=current.get(CONF_TTS_VOICE, ""),
                ): selector.TextSelector(),
                vol.Required(
                    CONF_SUPPRESS_LOCAL_AUDIO,
                    default=current.get(CONF_SUPPRESS_LOCAL_AUDIO, True),
                ): selector.BooleanSelector(),
                vol.Required(
                    CONF_PROACTIVE_VOICE_OUTPUT,
                    default=current.get(CONF_PROACTIVE_VOICE_OUTPUT, False),
                ): selector.BooleanSelector(),
            }
        )
        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
        )
