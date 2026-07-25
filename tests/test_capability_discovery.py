import unittest
from jarvis.homeassistant.capability_discovery import HomeAssistantCapabilityDiscovery
class C:
 async def get_services(self):return {"light":{"turn_on":{"fields":{"brightness":{}}}}}
 async def get_states(self):return [{"entity_id":"light.kitchen"}]
class Tests(unittest.IsolatedAsyncioTestCase):
 async def test_discovers_services_and_entities(self):
  catalog=await HomeAssistantCapabilityDiscovery(C()).discover()
  self.assertEqual(catalog.services[0].fields,frozenset({"brightness"}));self.assertEqual(catalog.entity_ids,frozenset({"light.kitchen"}))
