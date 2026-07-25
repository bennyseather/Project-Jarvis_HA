"""Safe coordinator for the first end-to-end Jarvis assistant slice."""

from __future__ import annotations

from jarvis.models.assistant_slice import AssistantInput, AssistantProposalKind, HomeAssistantReadProvider, LanguageModelProvider


class AssistantOrchestrator:
    """Accept only conversational and allow-listed read-only proposals."""

    def __init__(self, language_model: LanguageModelProvider, home_assistant: HomeAssistantReadProvider,
                 allowed_entity_ids: frozenset[str] = frozenset()) -> None:
        self._language_model, self._home_assistant = language_model, home_assistant
        self._allowed_entity_ids = allowed_entity_ids

    async def handle(self, request_text: str, context: dict[str, object] | None = None) -> dict[str, object]:
        proposal = self._language_model.propose(AssistantInput(request_text, {} if context is None else context))
        if proposal.kind is AssistantProposalKind.CONVERSATION:
            return {"status": "success", "message": proposal.message}
        if proposal.kind is AssistantProposalKind.READ_ENTITY_STATE:
            if proposal.entity_id not in self._allowed_entity_ids:
                return {"status": "not_supported", "message": "That entity is not available."}
            try:
                state = await self._home_assistant.read_entity_state(proposal.entity_id)
            except Exception:
                return {"status": "unavailable", "message": "Home Assistant data is unavailable."}
            return {"status": "success", "message": proposal.message, "entity_id": state.entity_id,
                    "state": state.state, "attributes": dict(state.attributes)}
        return {"status": "not_supported", "message": "That request is not supported."}
