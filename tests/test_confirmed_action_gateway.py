import unittest
from datetime import datetime,timezone
from jarvis.homeassistant.action_gateway import ConfirmedHomeAssistantActionGateway
from jarvis.homeassistant.capability_gateway import HomeAssistantCapabilityGateway
from jarvis.homeassistant.pending_actions import PendingActionStore
from jarvis.homeassistant.risk_policy import HomeAssistantRiskPolicy
from jarvis.models.home_assistant_gateway import HomeAssistantActionProposal,HomeAssistantCapabilityCatalog,HomeAssistantServiceDefinition
class C:
 def __init__(self):self.calls=[]
 async def call_service(self,*a):self.calls.append(a)
class PartialC(C):
 async def call_service(self,*a):
  self.calls.append(a)
  if "light.failed" in a[2]["entity_id"]:raise RuntimeError("unavailable")
 async def get_states(self):
  return [
   {"entity_id":"light.kitchen","state":"on"},
   {"entity_id":"light.failed","state":"unavailable"},
  ]
class AppliedDespiteErrorC(PartialC):
 async def get_states(self):
  return [
   {"entity_id":"light.kitchen","state":"on"},
   {"entity_id":"light.failed","state":"on"},
  ]
class DeferredC(C):
 def __init__(self):
  super().__init__();self.release=None
 async def dispatch_service(self,*a):
  self.calls.append(a);self.release=__import__("asyncio").Event()
  async def finish():await self.release.wait();return True
  return __import__("asyncio").create_task(finish())
class Tests(unittest.IsolatedAsyncioTestCase):
 async def test_confirmed_once(self):
  c=C();p=HomeAssistantActionProposal("light","turn_on",("light.kitchen",),summary="Turn on kitchen")
  g=ConfirmedHomeAssistantActionGateway(HomeAssistantCapabilityGateway(HomeAssistantCapabilityCatalog((HomeAssistantServiceDefinition("light","turn_on"),),frozenset({"light.kitchen"}))),HomeAssistantRiskPolicy({"light.turn_on"},allowed_entities={"light.kitchen"}),PendingActionStore(lambda:datetime(2026,1,1,tzinfo=timezone.utc)),c)
  pending=g.request(p);self.assertEqual(pending["status"],"requires_confirmation")
  self.assertEqual((await g.confirm(pending["token"],p))["status"],"success");self.assertEqual(len(c.calls),1)
  self.assertEqual((await g.confirm(pending["token"],p))["status"],"forbidden");self.assertEqual(len(c.calls),1)
 async def test_immediate_action_needs_no_token(self):
  c=C();p=HomeAssistantActionProposal("light","turn_on",("light.kitchen",),summary="Turn on kitchen")
  g=ConfirmedHomeAssistantActionGateway(HomeAssistantCapabilityGateway(HomeAssistantCapabilityCatalog((HomeAssistantServiceDefinition("light","turn_on"),),frozenset({"light.kitchen"}))),HomeAssistantRiskPolicy(allowed_entities={"light.kitchen"},immediate_services={"light.turn_on"}),PendingActionStore(),c)
  self.assertEqual(g.request(p)["status"],"immediate_action")
  result=await g.execute_immediate(p)
  self.assertEqual(result["status"],"success");self.assertEqual(result["message"],"Action completed for 1 device.");self.assertEqual(len(c.calls),1)
 async def test_immediate_multi_device_action_reports_partial_outcomes(self):
  c=PartialC();entities=frozenset({"light.kitchen","light.failed"});p=HomeAssistantActionProposal("light","turn_on",tuple(sorted(entities)))
  g=ConfirmedHomeAssistantActionGateway(HomeAssistantCapabilityGateway(HomeAssistantCapabilityCatalog((HomeAssistantServiceDefinition("light","turn_on"),),entities)),HomeAssistantRiskPolicy(allowed_entities=entities,immediate_services={"light.turn_on"}),PendingActionStore(),c)
  result=await g.execute_immediate(p)
  self.assertEqual(result["status"],"success");self.assertEqual(result["message"],"Action completed for 1 device. 1 device was unavailable.");self.assertEqual(result["succeeded"],("light.kitchen",));self.assertEqual(result["failed"],("light.failed",));self.assertEqual(len(c.calls),1)
 async def test_multi_device_error_is_reconciled_from_resulting_states(self):
  c=AppliedDespiteErrorC();entities=frozenset({"light.kitchen","light.failed"});p=HomeAssistantActionProposal("light","turn_on",tuple(sorted(entities)))
  g=ConfirmedHomeAssistantActionGateway(HomeAssistantCapabilityGateway(HomeAssistantCapabilityCatalog((HomeAssistantServiceDefinition("light","turn_on"),),entities)),HomeAssistantRiskPolicy(allowed_entities=entities,immediate_services={"light.turn_on"}),PendingActionStore(),c)
  result=await g.execute_immediate(p)
  self.assertEqual(result["status"],"success");self.assertEqual(result["succeeded"],("light.failed","light.kitchen"));self.assertEqual(result["failed"],());self.assertEqual(result["message"],"Action completed for 2 devices.");self.assertEqual(len(c.calls),1)
 async def test_slow_service_completion_returns_bounded_acknowledgement(self):
  c=DeferredC();entities=frozenset({"light.kitchen","light.office"});p=HomeAssistantActionProposal("light","turn_on",tuple(sorted(entities)))
  g=ConfirmedHomeAssistantActionGateway(HomeAssistantCapabilityGateway(HomeAssistantCapabilityCatalog((HomeAssistantServiceDefinition("light","turn_on"),),entities)),HomeAssistantRiskPolicy(allowed_entities=entities,immediate_services={"light.turn_on"}),PendingActionStore(),c)
  loop=__import__("asyncio").get_running_loop();started=loop.time();result=await g.execute_immediate(p)
  self.assertLess(loop.time()-started,1.2);self.assertEqual(result["message"],"Action sent to 2 devices.");self.assertTrue(result["completion_pending"])
  c.release.set();await __import__("asyncio").sleep(0)
