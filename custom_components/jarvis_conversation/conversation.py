from homeassistant.components import conversation
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import intent

async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([JarvisConversationEntity(hass, entry)])

class JarvisConversationEntity(conversation.ConversationEntity):
    _attr_name = "Project Jarvis"
    def __init__(self, hass, entry): self.hass, self.entry = hass, entry
    @property
    def supported_languages(self): return "*"
    async def _async_handle_message(self, user_input, chat_log):
        session = async_get_clientsession(self.hass)
        async with session.post(
            self.entry.data["bridge_url"] + "/v1/conversation",
            json={
                "text": user_input.text,
                "conversation_id": user_input.conversation_id,
            },
            headers={"Authorization": "Bearer " + self.entry.data["api_key"]},
            timeout=60,
        ) as response:
            payload = await response.json()
        answer = payload.get("message", "Jarvis is unavailable.")
        result = intent.IntentResponse(language=user_input.language)
        result.async_set_speech(answer)
        return conversation.ConversationResult(conversation_id=user_input.conversation_id, response=result, continue_conversation=payload.get("status") == "requires_confirmation")
