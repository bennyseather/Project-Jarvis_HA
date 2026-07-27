"""Authenticated conversation boundary used by the Home Assistant add-on."""
from __future__ import annotations


class JarvisConversationBridge:
    """Expose only Jarvis's existing request and confirmation lifecycle."""
    def __init__(self, application) -> None:
        self._application = application

    async def process(
        self,
        text: str,
        confirmation_token: str | None = None,
        conversation_id: str | None = None,
    ) -> dict[str, object]:
        if confirmation_token is None and text.strip().startswith("confirm "):
            confirmation_token = text.strip().split(maxsplit=1)[1]
        if confirmation_token is not None:
            store = getattr(self._application.container, "conversation_store", None)
            identifier = (
                "local-default"
                if store is None
                else store.normalize_conversation_id(conversation_id)
            )
            if store is not None and text.strip():
                store.add_message(identifier, "user", text)
            pending = self._application._pending_action_payloads.pop(confirmation_token, None)
            if pending is None:
                return {"status":"forbidden","message":"Confirmation is invalid."}
            pending_conversation, payload = pending
            if pending_conversation != identifier:
                return {"status":"forbidden","message":"Confirmation belongs to another conversation."}
            result = await self._application.container.read_only_assistant.confirm_action(confirmation_token, payload)
            message = self._application._user_message(result)
            if store is not None:
                store.add_message(identifier, "assistant", message)
            return {"status":result["status"],"message":message}
        result = (
            await self._application.handle_request(text)
            if conversation_id is None
            else await self._application.handle_request(text, conversation_id)
        )
        if result.get("status") == "requires_confirmation":
            token, payload = result.get("token"), result.pop("action_payload", None)
            if token and payload:
                store = getattr(self._application.container, "conversation_store", None)
                identifier = (
                    "local-default"
                    if store is None
                    else store.normalize_conversation_id(conversation_id)
                )
                self._application._pending_action_payloads[token] = (identifier, payload)
                summary = result.get("summary", "Confirmation is required.")
                return {
                    "status": "requires_confirmation",
                    "message": f"Confirm action: {summary}. Reply: confirm {token}",
                    "confirmation_token": token,
                }
            token = result.get("token")
            if token:
                command = result.get("confirmation_command", "memory confirm")
                return {"status": "requires_confirmation", "message": f"{result.get('message', 'Confirmation is required.')} Reply: {command} {token}"}
        return {"status":result.get("status", "unavailable"),"message":self._application._user_message(result)}
