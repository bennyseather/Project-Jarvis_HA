"""Configuration flow for Project Jarvis Conversation."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.helpers import selector
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
