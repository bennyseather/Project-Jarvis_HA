import unittest
from jarvis.homeassistant.access_policy import resolve_entities
from jarvis.models.home_assistant_gateway import HomeAssistantCapabilityCatalog


class AccessPolicyTests(unittest.TestCase):
    def test_domains_expand_only_discovered_nonexcluded_entities(self):
        catalog = HomeAssistantCapabilityCatalog((), frozenset({"light.kitchen", "switch.fan", "camera.porch_camera", "sensor.polestar"}))
        self.assertEqual(resolve_entities(catalog, domains=("light", "switch"), excluded_entities=("switch.fan",)), frozenset({"light.kitchen"}))
