"""Authenticated conversation boundary used by the Home Assistant add-on."""
from __future__ import annotations


class JarvisConversationBridge:
    """Expose only Jarvis's existing request and confirmation lifecycle."""
    def __init__(self, application) -> None:
        self._application = application

    async def process(self, text: str, confirmation_token: str | None = None) -> dict[str, object]:
        if confirmation_token is None and text.strip().startswith("confirm "):
            confirmation_token = text.strip().split(maxsplit=1)[1]
        if confirmation_token is not None:
            payload = self._application._pending_action_payloads.pop(confirmation_token, None)
            if payload is None:
                return {"status":"forbidden","message":"Confirmation is invalid."}
            result = await self._application.container.read_only_assistant.confirm_action(confirmation_token, payload)
            return {"status":result["status"],"message":self._application._user_message(result)}
        result = await self._application.handle_request(text)
        if result.get("status") == "requires_confirmation":
            token, payload = result.get("token"), result.pop("action_payload", None)
            if token and payload:
                self._application._pending_action_payloads[token] = payload
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
