"""Composition helper for the safe read-only assistant slice."""
from jarvis.core.assistant_orchestrator import AssistantOrchestrator
from jarvis.homeassistant.read_adapter import HomeAssistantReadAdapter
from jarvis.providers.assistant_proposal_provider import OpenAIAssistantProposalProvider
def create_read_only_assistant(openai_provider, home_assistant_client, allowed_entity_ids=frozenset(), resolver=None):
 return AssistantOrchestrator(OpenAIAssistantProposalProvider(openai_provider),HomeAssistantReadAdapter(home_assistant_client),frozenset(allowed_entity_ids),resolver)
