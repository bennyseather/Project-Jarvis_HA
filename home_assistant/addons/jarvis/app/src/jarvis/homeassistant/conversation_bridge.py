"""Authenticated conversation boundary used by the Home Assistant add-on."""

from __future__ import annotations


class JarvisConversationBridge:
    """Expose Jarvis request, confirmation, and voice-friendly continuity."""

    _AFFIRMATIVE = {
        "yes", "yes please", "confirm", "confirmed", "do it", "go ahead",
        "proceed", "please do",
    }
    _NEGATIVE = {
        "no", "no thanks", "cancel", "never mind", "nevermind", "stop",
    }

    def __init__(self, application) -> None:
        self._application = application
        self._pending_by_conversation: dict[str, tuple[str, str]] = {}

    async def process(
        self,
        text: str,
        confirmation_token: str | None = None,
        conversation_id: str | None = None,
        voice_mode: bool = False,
        proactive_voice_route: dict[str, object] | None = None,
        source_id: str | None = None,
    ) -> dict[str, object]:
        identifier = self._conversation_identifier(conversation_id)
        delivery = getattr(
            self._application.container, "proactive_delivery", None
        )
        if delivery is not None:
            delivery.set_voice_route(proactive_voice_route)
        normalized = " ".join(text.casefold().split()).strip(" .?!")
        pending = self._pending_by_conversation.get(identifier)

        if pending is not None and normalized in self._NEGATIVE:
            self._pending_by_conversation.pop(identifier, None)
            kind, token = pending
            if kind == "action":
                self._application._pending_action_payloads.pop(token, None)
            else:
                self._application.container.natural_memory_controller.cancel_confirmation(
                    token
                )
            return self._record_simple(
                identifier, text, "Cancelled. I will not proceed.", "success"
            )
        if pending is not None and normalized in self._AFFIRMATIVE:
            self._pending_by_conversation.pop(identifier, None)
            kind, token = pending
            if kind == "action":
                return await self._confirm_action(token, identifier, text)
            return self._confirm_memory(token, identifier, text)

        if (
            confirmation_token is None
            and text.strip().startswith("confirm ")
            and not text.strip().casefold().startswith("confirm memory ")
        ):
            confirmation_token = text.strip().split(maxsplit=1)[1]
        if confirmation_token is not None:
            return await self._confirm_action(
                confirmation_token, identifier, text
            )

        result = await self._application.handle_request(
            text,
            conversation_id,
            voice_mode=voice_mode,
            source_id=source_id,
        )
        if result.get("status") == "requires_confirmation":
            action_token = result.get("token")
            action_payload = result.pop("action_payload", None)
            if action_token and action_payload:
                self._application._pending_action_payloads[action_token] = (
                    identifier,
                    action_payload,
                )
                self._pending_by_conversation[identifier] = (
                    "action",
                    action_token,
                )
                summary = str(result.get("summary", "That action requires confirmation."))
                message = (
                    f"{summary}. Shall I proceed?"
                    if voice_mode
                    else f"Confirm action: {summary}. Reply: confirm {action_token}"
                )
                return {
                    "status": "requires_confirmation",
                    "message": message,
                    "confirmation_token": action_token,
                }

            memory_token = result.get("confirmation_token") or result.get("token")
            if memory_token:
                self._pending_by_conversation[identifier] = (
                    "memory",
                    str(memory_token),
                )
                message = (
                    "That information appears private. Shall I remember it permanently?"
                    if voice_mode
                    else str(result.get("message", "Confirmation is required."))
                )
                return {
                    "status": "requires_confirmation",
                    "message": message,
                    "confirmation_token": memory_token,
                }
        return {
            "status": result.get("status", "unavailable"),
            "message": self._application._user_message(result),
        }

    async def _confirm_action(
        self, token: str, identifier: str, user_text: str
    ) -> dict[str, object]:
        store = getattr(self._application.container, "conversation_store", None)
        if store is not None and user_text.strip():
            store.add_message(identifier, "user", user_text)
        pending = self._application._pending_action_payloads.get(token)
        if pending is None:
            return {"status": "forbidden", "message": "Confirmation is invalid."}
        pending_conversation, payload = pending
        if pending_conversation != identifier:
            return {
                "status": "forbidden",
                "message": "Confirmation belongs to another conversation.",
            }
        self._application._pending_action_payloads.pop(token, None)
        if self._pending_by_conversation.get(identifier) == ("action", token):
            self._pending_by_conversation.pop(identifier, None)
        result = await self._application.container.read_only_assistant.confirm_action(
            token, payload
        )
        message = self._application._user_message(result)
        if store is not None:
            store.add_message(identifier, "assistant", message)
        return {"status": result["status"], "message": message}

    def _confirm_memory(
        self, token: str, identifier: str, user_text: str
    ) -> dict[str, object]:
        store = getattr(self._application.container, "conversation_store", None)
        if store is not None and user_text.strip():
            store.add_message(identifier, "user", user_text)
        result = self._application.container.natural_memory_controller.handle(
            f"confirm memory {token}", identifier
        )
        if result is None:
            result = {
                "status": "forbidden",
                "message": "That memory confirmation is invalid or has expired.",
            }
        message = self._application._user_message(result)
        if store is not None:
            store.add_message(identifier, "assistant", message)
        return {"status": result.get("status", "unavailable"), "message": message}

    def _record_simple(
        self, identifier: str, user_text: str, message: str, status: str
    ) -> dict[str, object]:
        store = getattr(self._application.container, "conversation_store", None)
        if store is not None:
            if user_text.strip():
                store.add_message(identifier, "user", user_text)
            store.add_message(identifier, "assistant", message)
        return {"status": status, "message": message}

    def _conversation_identifier(self, conversation_id: str | None) -> str:
        store = getattr(self._application.container, "conversation_store", None)
        return (
            "local-default"
            if store is None
            else store.normalize_conversation_id(conversation_id)
        )
