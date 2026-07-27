"""Home Assistant conversation and external voice-output adapter."""

from __future__ import annotations

import asyncio
import logging

from homeassistant.components import conversation
from homeassistant.components.conversation import AssistantContent
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import intent
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .voice import (
    build_tts_service_data,
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
        external_voice = should_route_external(
            self.entry.options, user_input.device_id
        )
        session = async_get_clientsession(self.hass)
        async with session.post(
            self.entry.data["bridge_url"] + "/v1/conversation",
            json={
                "text": user_input.text,
                "conversation_id": conversation_id,
                "voice_mode": external_voice,
                "device_id": user_input.device_id,
                "satellite_id": user_input.satellite_id,
            },
            headers={"Authorization": "Bearer " + self.entry.data["api_key"]},
            timeout=60,
        ) as response:
            response.raise_for_status()
            payload = await response.json()

        answer = str(payload.get("message", "Jarvis is unavailable."))
        chat_log.async_add_assistant_content_without_tools(
            AssistantContent(agent_id=user_input.agent_id, content=answer)
        )

        routed = False
        if external_voice:
            routed = await self._async_speak_externally(answer, user_input.context)

        result = intent.IntentResponse(language=user_input.language)
        result.async_set_speech(
            "" if routed and suppress_local_audio(self.entry.options) else answer
        )
        return conversation.ConversationResult(
            conversation_id=conversation_id,
            response=result,
            continue_conversation=payload.get("status")
            == "requires_confirmation",
        )

    async def _async_speak_externally(self, message, context) -> bool:
        output_entity = self.entry.options.get(
            "output_media_player_entity_id"
        )
        output_state = self.hass.states.get(output_entity)
        if output_state is None or output_state.state == "unavailable":
            LOGGER.warning("Jarvis external voice output is unavailable: %s", output_entity)
            return False
        try:
            await self.hass.services.async_call(
                "tts",
                "speak",
                build_tts_service_data(self.entry.options, message),
                blocking=True,
                context=context,
            )
        except (HomeAssistantError, asyncio.TimeoutError) as error:
            LOGGER.warning("Jarvis external TTS failed; using local response: %s", error)
            return False
        return True
