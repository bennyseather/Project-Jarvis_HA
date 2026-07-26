import unittest
from jarvis.homeassistant.access_policy import resolve_entities
from jarvis.models.home_assistant_gateway import HomeAssistantCapabilityCatalog


class AccessPolicyTests(unittest.TestCase):
    def test_domains_expand_only_discovered_nonexcluded_entities(self):
        catalog = HomeAssistantCapabilityCatalog((), frozenset({"light.kitchen", "switch.fan", "camera.porch_camera", "sensor.polestar"}))
        self.assertEqual(resolve_entities(catalog, domains=("light", "switch"), excluded_entities=("switch.fan",)), frozenset({"light.kitchen"}))

    def test_protected_domains_need_an_explicit_read_only_exception(self):
        catalog = HomeAssistantCapabilityCatalog((), frozenset({"camera.porch_camera", "lock.front_door"}))
        self.assertEqual(resolve_entities(catalog, entity_ids=("camera.porch_camera", "lock.front_door"), read_only_exceptions=("camera.porch_camera",)), frozenset({"camera.porch_camera"}))
