"""Home Assistant conversation and external voice-output adapter."""

from __future__ import annotations

import asyncio
import logging
from urllib.parse import unquote

from homeassistant.components import conversation
from homeassistant.components.conversation import AssistantContent
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import intent
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import entity_registry as er

from .voice import (
    build_tts_service_data,
    sanitize_spoken_reply,
    should_route_external,
    suppress_local_audio,
)

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([JarvisConversationEntity(hass, entry)])


class JarvisConversationEntity(conversation.ConversationEntity):
    _attr_name = "Project Jarvis"

    def __init__(self, hass, entry):
        self.hass, self.entry = hass, entry

    @property
    def supported_languages(self):
        return "*"

    async def _async_handle_message(self, user_input, chat_log):
        conversation_id = user_input.conversation_id or chat_log.conversation_id
        browser_target = self._browser_voice_target(conversation_id)
        satellite_device_id = None
        if user_input.satellite_id:
            satellite = er.async_get(self.hass).async_get(user_input.satellite_id)
            if satellite is not None:
                satellite_device_id = satellite.device_id
        external_voice = should_route_external(
            self.entry.options,
            user_input.device_id,
            satellite_device_id,
        )
        voice_mode = bool(
            external_voice
            or user_input.device_id
            or user_input.satellite_id
            or browser_target
        )
        source_id = (
            user_input.device_id
            or satellite_device_id
            or user_input.satellite_id
            or getattr(user_input.context, "user_id", None)
            or f"entry:{self.entry.entry_id}"
        )
        if self.entry.options.get("external_voice_output") and not external_voice:
            LOGGER.warning(
                "Jarvis external voice source did not match: configured=%s, "
                "device=%s, satellite=%s, satellite_device=%s",
                self.entry.options.get("input_device_id"),
                user_input.device_id,
                user_input.satellite_id,
                satellite_device_id,
            )
        session = async_get_clientsession(self.hass)
        proactive_voice_route = None
        if external_voice:
            proactive_voice_route = {
                "tts_entity_id": self.entry.options.get("tts_entity_id"),
                "media_player_entity_id": self.entry.options.get(
                    "output_media_player_entity_id"
                ),
                "language": self.entry.options.get("tts_language", ""),
                "voice": self.entry.options.get("tts_voice", ""),
            }
        elif voice_mode:
            proactive_voice_route = {
                "event_type": "jarvis_voice_follow_up",
                "source_id": source_id,
                "target_id": (
                    browser_target
                    or (
                        source_id
                        if user_input.device_id or satellite_device_id or user_input.satellite_id
                        else "development_computer"
                    )
                ),
            }
        async with session.post(
            self.entry.data["bridge_url"] + "/v1/conversation",
            json={
                "text": user_input.text,
                "conversation_id": conversation_id,
                "source_id": source_id,
                "voice_mode": voice_mode,
                "device_id": user_input.device_id,
                "satellite_id": user_input.satellite_id,
                "activation_id": getattr(user_input.context, "id", None),
                "proactive_voice_route": proactive_voice_route,
            },
            headers={"Authorization": "Bearer " + self.entry.data["api_key"]},
            timeout=60,
        ) as response:
            response.raise_for_status()
            payload = await response.json()

        answer = str(payload.get("message", "Jarvis is unavailable."))
        if voice_mode:
            answer = sanitize_spoken_reply(answer)
        chat_log.async_add_assistant_content_without_tools(
            AssistantContent(agent_id=user_input.agent_id, content=answer)
        )

        routed = False
        browser_progress = bool(
            browser_target and payload.get("status") == "in_progress" and answer
        )
        if browser_progress:
            # Keep both stages of a slow browser request on one scoped delivery
            # channel. Letting Assist speak the progress result while Jarvis
            # dispatches the final follow-up creates two independent browser
            # playback paths and allows retained HA media to leak between them.
            self.hass.bus.async_fire(
                "jarvis_voice_follow_up",
                {
                    "message": answer,
                    "source_id": str(source_id)[:200],
                    "target_id": str(browser_target)[:200],
                    "conversation_id": str(conversation_id)[:200],
                    "session_id": str(conversation_id)[:200],
                    "delivery_id": f"progress:{getattr(user_input.context, 'id', conversation_id)}",
                    "sequence": 0,
                },
                context=user_input.context,
            )
            routed = True
        if external_voice:
            routed = await self._async_speak_externally(answer, user_input.context)

        result = intent.IntentResponse(language=user_input.language)
        # Omit speech entirely when another delivery path owns it. An empty
        # speech field can still enter HA's TTS stage and replay cached audio.
        if not (browser_progress or (routed and suppress_local_audio(self.entry.options))):
            result.async_set_speech(answer)
        return conversation.ConversationResult(
            conversation_id=conversation_id,
            response=result,
            continue_conversation=payload.get("status")
            == "requires_confirmation",
        )

    @staticmethod
    def _browser_voice_target(conversation_id):
        """Read the explicit target carried by a Jarvis browser voice session."""
        value = str(conversation_id or "")
        if not value.startswith("jarvis-voice:"):
            return None
        parts = value.split(":", 2)
        target = unquote(parts[1]).strip() if len(parts) == 3 else ""
        return target[:200] if target and all(
            character.isalnum() or character in "_-" for character in target
        ) else None

    async def _async_speak_externally(self, message, context) -> bool:
        output_entity = self.entry.options.get(
            "output_media_player_entity_id"
        )
        output_state = self.hass.states.get(output_entity)
        if output_state is None or output_state.state == "unavailable":
            LOGGER.warning("Jarvis external voice output is unavailable: %s", output_entity)
            return False
        service_data = build_tts_service_data(self.entry.options, message)
        try:
            await self.hass.services.async_call(
                "tts",
                "speak",
                service_data,
                blocking=True,
                context=context,
            )
        except (HomeAssistantError, asyncio.TimeoutError) as error:
            if "language" not in service_data and "options" not in service_data:
                LOGGER.warning(
                    "Jarvis external TTS failed; using local response: %s", error
                )
                return False
            LOGGER.warning(
                "Jarvis external TTS rejected the configured language or voice; "
                "retrying with provider defaults: %s",
                error,
            )
            service_data.pop("language", None)
            service_data.pop("options", None)
            try:
                await self.hass.services.async_call(
                    "tts",
                    "speak",
                    service_data,
                    blocking=True,
                    context=context,
                )
            except (HomeAssistantError, asyncio.TimeoutError) as retry_error:
                LOGGER.warning(
                    "Jarvis external TTS failed; using local response: %s",
                    retry_error,
                )
                return False
        return True
