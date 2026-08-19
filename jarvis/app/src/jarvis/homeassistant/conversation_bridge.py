"""Authenticated conversation boundary used by the Home Assistant add-on."""

from __future__ import annotations

import re
from collections import deque


class JarvisConversationBridge:
    """Expose Jarvis request, confirmation, and voice-friendly continuity."""

    _AFFIRMATIVE = {
        "yes", "yes please", "confirm", "confirmed", "do it", "go ahead",
        "proceed", "please do", "approve", "approved",
    }
    _NEGATIVE = {
        "no", "no thanks", "cancel", "never mind", "nevermind", "stop",
    }

    def __init__(self, application) -> None:
        self._application = application
        self._pending_by_conversation: dict[str, tuple[str, str]] = {}
        self._recent_activations: deque[str] = deque(maxlen=128)
        self._activation_results: dict[str, dict[str, object]] = {}

    async def process(
        self,
        text: str,
        confirmation_token: str | None = None,
        conversation_id: str | None = None,
        voice_mode: bool = False,
        proactive_voice_route: dict[str, object] | None = None,
        source_id: str | None = None,
        activation_id: str | None = None,
    ) -> dict[str, object]:
        identifier = self._conversation_identifier(conversation_id)
        activation_key = (
            f"{identifier}:{source_id or 'unknown'}:{activation_id}"
            if activation_id else None
        )
        if activation_key and activation_key in self._activation_results:
            return dict(self._activation_results[activation_key])
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
                compound = getattr(
                    self._application.container, "compound_orchestration", None
                )
                if compound is not None:
                    compound.cancel(token)
                blueprint = getattr(
                    self._application.container, "blueprint_planner", None
                )
                if blueprint is not None:
                    blueprint.cancel(token)
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

        request_text = text
        if pending is not None and pending[0] == "action":
            self._pending_by_conversation.pop(identifier, None)
            token = pending[1]
            self._application._pending_action_payloads.pop(token, None)
            compound = getattr(
                self._application.container, "compound_orchestration", None
            )
            if compound is not None:
                compound.cancel(token)
            blueprint = getattr(
                self._application.container, "blueprint_planner", None
            )
            if blueprint is not None:
                blueprint.cancel(token)
            request_text = re.sub(
                r"^\s*(?:(?:actually|instead|change that to|rather|just)\b[\s,:-]*)+",
                "",
                text,
                flags=re.IGNORECASE,
            ) or text

        operation = self._application.handle_request(
            request_text,
            conversation_id,
            voice_mode=voice_mode,
            source_id=source_id,
        )
        intelligence = getattr(
            self._application.container, "efficient_intelligence", None
        )
        if intelligence is not None:
            operation = intelligence.execute(
                operation, text=request_text, source_id=source_id
            )
        coordinator = getattr(
            self._application.container, "responsive_voice", None
        )
        if voice_mode and coordinator is not None:
            result = await coordinator.execute(
                operation,
                text=request_text,
                conversation_id=identifier,
                source_id=source_id,
                route=proactive_voice_route,
            )
        else:
            result = await operation
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
                response = {
                    "status": "requires_confirmation",
                    "message": message,
                    "confirmation_token": action_token,
                }
                self._remember_activation(activation_key, response)
                return response

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
                response = {
                    "status": "requires_confirmation",
                    "message": message,
                    "confirmation_token": memory_token,
                }
                self._remember_activation(activation_key, response)
                return response
        response = {
            "status": result.get("status", "unavailable"),
            "message": self._application._user_message(result),
        }
        self._remember_activation(activation_key, response)
        return response

    def _remember_activation(
        self, activation_id: str | None, response: dict[str, object]
    ) -> None:
        """Cache one bounded result so a repeated wake run cannot execute twice."""
        if not activation_id:
            return
        if len(self._recent_activations) == self._recent_activations.maxlen:
            expired = self._recent_activations[0]
            self._activation_results.pop(expired, None)
        self._recent_activations.append(activation_id)
        self._activation_results[activation_id] = dict(response)

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
        if payload.get("kind") == "compound_plan":
            result = await self._application.container.compound_orchestration.confirm(
                token, payload
            )
        elif payload.get("kind") == "stewardship_mode":
            result = await self._application.container.stewardship.confirm(
                token, payload
            )
        elif payload.get("kind") == "adaptive_preference":
            result = self._application.container.adaptive_preferences.confirm(
                token, payload
            )
        elif payload.get("kind") == "routine_automation":
            result = self._application.container.contextual_routines.confirm(
                token, payload
            )
        elif payload.get("kind") == "blueprint_install":
            result = self._application.container.blueprint_planner.confirm(
                token, payload
            )
        else:
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
