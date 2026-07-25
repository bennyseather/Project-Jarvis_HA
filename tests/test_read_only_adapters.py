import unittest
from jarvis.homeassistant.read_adapter import HomeAssistantReadAdapter
from jarvis.models.assistant_slice import AssistantInput,AssistantProposalKind
from jarvis.providers.assistant_proposal_provider import OpenAIAssistantProposalProvider
class OpenAI:
 def __init__(self,v):self.v=v
 def ask(self,x):return self.v
class HA:
 async def get_states(self):return [{"entity_id":"light.kitchen","state":"on","attributes":{"x":1}}]
class Tests(unittest.IsolatedAsyncioTestCase):
 async def test_adapters_validate_and_read(self):
  p=OpenAIAssistantProposalProvider(OpenAI('{"kind":"read_entity_state","entity_id":"light.kitchen"}')).propose(AssistantInput("state"))
  self.assertEqual(p.kind,AssistantProposalKind.READ_ENTITY_STATE)
  self.assertEqual((await HomeAssistantReadAdapter(HA()).read_entity_state("light.kitchen")).state,"on")
 def test_bad_model_output_is_unsupported(self):
  self.assertEqual(OpenAIAssistantProposalProvider(OpenAI("bad")).propose(AssistantInput("x")).kind,AssistantProposalKind.UNSUPPORTED)
