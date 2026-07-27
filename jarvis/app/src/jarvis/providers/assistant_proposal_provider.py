"""Schema-validating OpenAI adapter for the safe assistant slice."""
from __future__ import annotations

import json

from jarvis.models.assistant_slice import AssistantInput, AssistantProposal, AssistantProposalKind
from jarvis.persona import DEFAULT_PERSONA


_INSTRUCTIONS = """You are the language and planning layer for Project Jarvis.
Return JSON only with kind conversation, read_entity_state, or home_assistant_action.
For read_entity_state include entity_id. For home_assistant_action include action with
domain, service, entity_ids, service_data, and summary. For conversation include message.
Use only the Home Assistant entities, services, friendly names, areas, and groups supplied
in context. Treat the alternating message history as the current bounded conversation.
Resolve words such as it, them, all, the rest, and that area from the immediately preceding
turns when one named entity, area, or group is the clear referent. Preserve the referenced
group or area for a follow-up status question; do not turn a status question into an action.
Ask for clarification when more than one referent remains plausible."""


class OpenAIAssistantProposalProvider:
    def __init__(self, provider, persona=DEFAULT_PERSONA) -> None:
        self._provider = provider
        self._instructions = _INSTRUCTIONS + "\n" + persona.model_instructions()

    def propose(self, request: AssistantInput) -> AssistantProposal:
        context = dict(request.context)
        history = context.pop("conversation", ())
        messages = [
            {"role": item["role"], "content": item["content"]}
            for item in history
            if isinstance(item, dict)
            and item.get("role") in {"user", "assistant"}
            and isinstance(item.get("content"), str)
        ]
        messages.append({
            "role": "user",
            "content": json.dumps(
                {"request": request.request_text, "context": context},
                separators=(",", ":"),
            ),
        })
        model_request = {"instructions": self._instructions, "input": messages}
        try: payload=json.loads(self._provider.ask(model_request))
        except Exception: return AssistantProposal(AssistantProposalKind.UNSUPPORTED,"Unable to interpret the request.")
        try: kind=AssistantProposalKind(payload["kind"])
        except (KeyError, ValueError, TypeError): return AssistantProposal(AssistantProposalKind.UNSUPPORTED,"Unsupported model proposal.")
        if kind is AssistantProposalKind.READ_ENTITY_STATE and not isinstance(payload.get("entity_id"),str): return AssistantProposal(AssistantProposalKind.UNSUPPORTED,"Invalid entity proposal.")
        if kind is AssistantProposalKind.HOME_ASSISTANT_ACTION:
            action = payload.get("action")
            if (not isinstance(action, dict) or not isinstance(action.get("domain"), str)
                    or not isinstance(action.get("service"), str)
                    or not isinstance(action.get("entity_ids", ()), list)
                    or not all(isinstance(entity, str) for entity in action.get("entity_ids", ()))
                    or not isinstance(action.get("service_data", {}), dict)
                    or not isinstance(action.get("summary"), str)):
                return AssistantProposal(AssistantProposalKind.UNSUPPORTED,"Invalid action proposal.")
            action["entity_ids"] = tuple(action.get("entity_ids", ()))
            return AssistantProposal(kind, str(payload.get("message", "")), action=action)
        if kind not in {AssistantProposalKind.CONVERSATION,AssistantProposalKind.READ_ENTITY_STATE}: return AssistantProposal(AssistantProposalKind.UNSUPPORTED,"Unsupported model proposal.")
        return AssistantProposal(kind,str(payload.get("message","")),payload.get("entity_id"))
