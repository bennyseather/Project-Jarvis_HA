import json
import unittest
from jarvis.homeassistant.read_adapter import HomeAssistantReadAdapter
from jarvis.models.assistant_slice import AssistantInput,AssistantProposalKind
from jarvis.providers.assistant_proposal_provider import OpenAIAssistantProposalProvider
class OpenAI:
 def __init__(self,v):self.v=v;self.request=None
 def ask(self,x):self.request=x;return self.v
class HA:
 async def get_states(self):return [{"entity_id":"light.kitchen","state":"on","attributes":{"x":1}}]
class Tests(unittest.IsolatedAsyncioTestCase):
 async def test_adapters_validate_and_read(self):
  p=OpenAIAssistantProposalProvider(OpenAI('{"kind":"read_entity_state","entity_id":"light.kitchen"}')).propose(AssistantInput("state"))
  self.assertEqual(p.kind,AssistantProposalKind.READ_ENTITY_STATE)
  self.assertEqual((await HomeAssistantReadAdapter(HA()).read_entity_state("light.kitchen")).state,"on")
 def test_bad_model_output_is_unsupported(self):
  self.assertEqual(OpenAIAssistantProposalProvider(OpenAI("bad")).propose(AssistantInput("x")).kind,AssistantProposalKind.UNSUPPORTED)
 def test_action_schema_is_structurally_validated(self):
  provider=OpenAIAssistantProposalProvider(OpenAI('{"kind":"home_assistant_action","action":{"domain":"light","service":"turn_on","entity_ids":["light.kitchen"],"service_data":{},"summary":"Turn on kitchen"}}'))
  self.assertEqual(provider.propose(AssistantInput("turn on kitchen")).kind,AssistantProposalKind.HOME_ASSISTANT_ACTION)
 def test_model_receives_capability_context(self):
  model=OpenAI('{"kind":"conversation","message":"Hi"}')
  context={"home_assistant":{"action_entities":["light.blocks"]},"conversation":(
   {"role":"user","content":"What about the blocks?"},
   {"role":"assistant","content":"The blocks are off."},
  )}
  OpenAIAssistantProposalProvider(model).propose(AssistantInput("turn them on",context))
  self.assertIn("Return JSON only",model.request["instructions"])
  self.assertEqual(model.request["input"][:2],list(context["conversation"]))
  current=json.loads(model.request["input"][-1]["content"])
  self.assertEqual(current["request"],"turn them on")
  self.assertEqual(current["context"]["home_assistant"]["action_entities"],["light.blocks"])
  self.assertNotIn("conversation",current["context"])
