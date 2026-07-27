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
                    if not matches:
                        return {"status": "clarification_required", "message": "Please specify a configured action entity."}
                    resolved.extend(matches)
                if len(set(resolved)) != len(resolved):
                    return {"status": "clarification_required", "message": "Please specify the exact configured entity you mean."}
                action_data["entity_ids"] = tuple(resolved)
            action = HomeAssistantActionProposal(**action_data)
            result = self._action_gateway.request(action)
            if result.get("reason_code") == "unknown_entity":
                return {"status": "clarification_required", "message": "Please specify a configured action entity."}
            if result.get("reason_code") == "unknown_service":
                return {"status": "clarification_required", "message": "Please specify a configured service."}
            if result.get("status") == "requires_confirmation":
                result["action_payload"] = dict(action_data)
            if result.get("status") == "immediate_action":
                return await self._action_gateway.execute_immediate(action)
            return result
        if proposal.kind is AssistantProposalKind.READ_ENTITY_STATE:
            if self._resolver is not None:
                matches = self._resolver.resolve(proposal.entity_id or "")
                if not matches:
                    return {"status": "not_supported", "message": "That entity is not available."}
                if len(matches) > 20:
                    return {"status": "clarification_required", "message": "Please specify a smaller configured group or area."}
                if len(matches) > 1:
                    return await self._read_summary(matches)
                proposal = type(proposal)(proposal.kind, proposal.message, matches[0])
            if proposal.entity_id not in self._allowed_entity_ids:
                return {"status": "not_supported", "message": "That entity is not available."}
            try:
                state = await self._home_assistant.read_entity_state(proposal.entity_id)
            except Exception:
                return {"status": "unavailable", "message": "Home Assistant data is unavailable."}
            return {"status": "success", "message": f"{state.entity_id} is {state.state}.", "entity_id": state.entity_id,
                    "state": state.state, "attributes": dict(state.attributes)}
        return {"status": "not_supported", "message": "That request is not supported."}

    async def _read_summary(self, entity_ids):
        states, unavailable = [], []
        for entity_id in entity_ids:
            if entity_id not in self._allowed_entity_ids:
                continue
            try:
                states.append(await self._home_assistant.read_entity_state(entity_id))
            except Exception:
                unavailable.append(entity_id)
        if not states:
            return {"status": "unavailable", "message": "Home Assistant data is unavailable."}
        counts = {}
        for state in states: counts[state.state] = counts.get(state.state, 0) + 1
        summary = ", ".join(f"{count} {value}" for value, count in sorted(counts.items()))
        details = ", ".join(f"{state.entity_id} is {state.state}" for state in states[:5])
        suffix = "" if not unavailable else f"; {len(unavailable)} unavailable"
        return {"status": "success", "message": f"{len(states)} devices: {summary}. {details}{suffix}", "entity_ids": tuple(state.entity_id for state in states)}

    async def confirm_action(self, token: str, action: dict[str, object]) -> dict[str, object]:
        """Execute one exact, previously confirmed action payload."""
        from jarvis.models.home_assistant_gateway import HomeAssistantActionProposal
        if self._action_gateway is None:
            return {"status": "not_supported", "message": "Actions are unavailable."}
        return await self._action_gateway.confirm(token, HomeAssistantActionProposal(**action))
