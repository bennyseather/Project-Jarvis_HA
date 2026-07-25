import unittest
from jarvis.homeassistant.capability_gateway import HomeAssistantCapabilityGateway
from jarvis.models.home_assistant_gateway import HomeAssistantActionProposal,HomeAssistantCapabilityCatalog,HomeAssistantServiceDefinition
class Tests(unittest.TestCase):
 def setUp(self):self.g=HomeAssistantCapabilityGateway(HomeAssistantCapabilityCatalog((HomeAssistantServiceDefinition("light","turn_on",frozenset({"brightness"})),),frozenset({"light.kitchen"})))
 def test_validation_fails_closed(self):
  self.assertEqual(self.g.validate(HomeAssistantActionProposal("light","turn_on",("light.kitchen",),{"brightness":1})),(True,"valid"))
  self.assertEqual(self.g.validate(HomeAssistantActionProposal("light","turn_off")),(False,"unknown_service"))
  self.assertEqual(self.g.validate(HomeAssistantActionProposal("light","turn_on",("light.other",))),(False,"unknown_entity"))
  self.assertEqual(self.g.validate(HomeAssistantActionProposal("light","turn_on",service_data={"unsafe":1})),(False,"unknown_service_field"))
