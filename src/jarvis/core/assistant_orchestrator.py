"""Safe coordinator for the first end-to-end Jarvis assistant slice."""

from __future__ import annotations

from jarvis.models.assistant_slice import AssistantInput, AssistantProposalKind, HomeAssistantReadProvider, LanguageModelProvider


class AssistantOrchestrator:
    """Accept only conversational and allow-listed read-only proposals."""

    def __init__(self, language_model: LanguageModelProvider, home_assistant: HomeAssistantReadProvider,
                 allowed_entity_ids: frozenset[str] = frozenset(), resolver=None, action_gateway=None) -> None:
        self._language_model, self._home_assistant = language_model, home_assistant
        self._allowed_entity_ids = allowed_entity_ids
        self._resolver = resolver
        self._action_gateway = action_gateway

    def set_action_gateway(self, action_gateway) -> None:
        """Attach the discovered runtime action gateway after Home Assistant connects."""
        self._action_gateway = action_gateway

    async def handle(self, request_text: str, context: dict[str, object] | None = None) -> dict[str, object]:
        proposal = self._language_model.propose(AssistantInput(request_text, {} if context is None else context))
        if proposal.kind is AssistantProposalKind.CONVERSATION:
            return {"status": "success", "message": proposal.message}
        if proposal.kind is AssistantProposalKind.HOME_ASSISTANT_ACTION:
            if self._action_gateway is None or not proposal.action:
                return {"status": "not_supported", "message": "Actions are unavailable."}
            from jarvis.models.home_assistant_gateway import HomeAssistantActionProposal
            action_data = dict(proposal.action)
            if self._resolver is not None:
                resolved = []
                for entity_id in action_data.get("entity_ids", ()):
                    matches = self._resolver.resolve(entity_id)
                    if len(matches) != 1:
                        return {"status": "clarification_required", "message": "Please specify a configured action entity."}
                    resolved.append(matches[0])
                action_data["entity_ids"] = tuple(resolved)
            action = HomeAssistantActionProposal(**action_data)
            result = self._action_gateway.request(action)
            if result.get("reason_code") == "unknown_entity":
                return {"status": "clarification_required", "message": "Please specify a configured action entity."}
            if result.get("reason_code") == "unknown_service":
                return {"status": "clarification_required", "message": "Please specify a configured service."}
            if result.get("status") == "requires_confirmation":
                result["action_payload"] = dict(action_data)
            return result
        if proposal.kind is AssistantProposalKind.READ_ENTITY_STATE:
            if self._resolver is not None:
                matches = self._resolver.resolve(proposal.entity_id or "")
                if len(matches) != 1:
                    return {"status": "clarification_required" if matches else "not_supported", "message": "Please clarify the entity." if matches else "That entity is not available."}
                proposal = type(proposal)(proposal.kind, proposal.message, matches[0])
            if proposal.entity_id not in self._allowed_entity_ids:
                return {"status": "not_supported", "message": "That entity is not available."}
            try:
                state = await self._home_assistant.read_entity_state(proposal.entity_id)
            except Exception:
                return {"status": "unavailable", "message": "Home Assistant data is unavailable."}
            return {"status": "success", "message": proposal.message, "entity_id": state.entity_id,
                    "state": state.state, "attributes": dict(state.attributes)}
        return {"status": "not_supported", "message": "That request is not supported."}

    async def confirm_action(self, token: str, action: dict[str, object]) -> dict[str, object]:
        """Execute one exact, previously confirmed action payload."""
        from jarvis.models.home_assistant_gateway import HomeAssistantActionProposal
        if self._action_gateway is None:
            return {"status": "not_supported", "message": "Actions are unavailable."}
        return await self._action_gateway.confirm(token, HomeAssistantActionProposal(**action))
