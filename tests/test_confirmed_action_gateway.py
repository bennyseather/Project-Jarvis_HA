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
class Tests(unittest.IsolatedAsyncioTestCase):
 async def test_confirmed_once(self):
  c=C();p=HomeAssistantActionProposal("light","turn_on",("light.kitchen",),summary="Turn on kitchen")
  g=ConfirmedHomeAssistantActionGateway(HomeAssistantCapabilityGateway(HomeAssistantCapabilityCatalog((HomeAssistantServiceDefinition("light","turn_on"),),frozenset({"light.kitchen"}))),HomeAssistantRiskPolicy({"light.turn_on"},allowed_entities={"light.kitchen"}),PendingActionStore(lambda:datetime(2026,1,1,tzinfo=timezone.utc)),c)
  pending=g.request(p);self.assertEqual(pending["status"],"requires_confirmation")
  self.assertEqual((await g.confirm(pending["token"],p))["status"],"success");self.assertEqual(len(c.calls),1)
  self.assertEqual((await g.confirm(pending["token"],p))["status"],"forbidden");self.assertEqual(len(c.calls),1)
