"""Schema-validating OpenAI adapter for the safe assistant slice."""
from __future__ import annotations
import json
from jarvis.models.assistant_slice import AssistantInput, AssistantProposal, AssistantProposalKind

class OpenAIAssistantProposalProvider:
    def __init__(self, provider) -> None: self._provider = provider
    def propose(self, request: AssistantInput) -> AssistantProposal:
        instruction={"request":request.request_text,"context":dict(request.context),"output":"JSON: kind conversation/read_entity_state, message, entity_id"}
        try: payload=json.loads(self._provider.ask(instruction))
        except Exception: return AssistantProposal(AssistantProposalKind.UNSUPPORTED,"Unable to interpret the request.")
        try: kind=AssistantProposalKind(payload["kind"])
        except (KeyError, ValueError, TypeError): return AssistantProposal(AssistantProposalKind.UNSUPPORTED,"Unsupported model proposal.")
        if kind is AssistantProposalKind.READ_ENTITY_STATE and not isinstance(payload.get("entity_id"),str): return AssistantProposal(AssistantProposalKind.UNSUPPORTED,"Invalid entity proposal.")
        if kind not in {AssistantProposalKind.CONVERSATION,AssistantProposalKind.READ_ENTITY_STATE}: return AssistantProposal(AssistantProposalKind.UNSUPPORTED,"Unsupported model proposal.")
        return AssistantProposal(kind,str(payload.get("message","")),payload.get("entity_id"))
