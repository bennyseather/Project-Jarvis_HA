import unittest
from jarvis.homeassistant.risk_policy import HomeAssistantRiskPolicy
from jarvis.models.home_assistant_gateway import HomeAssistantActionProposal,HomeAssistantRisk
class Tests(unittest.TestCase):
 def test_deny_default_and_configured_risk(self):
  p=HomeAssistantRiskPolicy({"light.turn_on"},{"lock.unlock"},{"light.kitchen","lock.front"})
  self.assertEqual(p.evaluate(HomeAssistantActionProposal("light","turn_on",("light.kitchen",))).risk,HomeAssistantRisk.CONFIRM_REQUIRED)
  self.assertEqual(p.evaluate(HomeAssistantActionProposal("lock","unlock",("lock.front",))).risk,HomeAssistantRisk.HIGH_IMPACT_CONFIRM_REQUIRED)
  self.assertEqual(p.evaluate(HomeAssistantActionProposal("script","run",("light.kitchen",))).risk,HomeAssistantRisk.FORBIDDEN)
