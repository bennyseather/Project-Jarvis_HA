import unittest

from jarvis.homeassistant.capability_context import HomeAssistantCapabilityContext
from jarvis.models.home_assistant_gateway import HomeAssistantCapabilityCatalog, HomeAssistantServiceDefinition


class CapabilityContextTests(unittest.TestCase):
    def test_context_intersects_discovery_with_configuration(self):
        catalog = HomeAssistantCapabilityCatalog(
            (HomeAssistantServiceDefinition("light", "turn_on", frozenset({"brightness"})), HomeAssistantServiceDefinition("light", "turn_off")),
            frozenset({"light.blocks", "light.private"}),
        )
        context = HomeAssistantCapabilityContext(catalog, ("light.blocks", "light.missing"), ("light.blocks",), ("light.turn_on",), {"blocks":"light.blocks", "private":"light.private"}).as_context()
        self.assertEqual(context["read_entities"], ("light.blocks",))
        self.assertEqual(context["action_entities"], ("light.blocks",))
        self.assertEqual(context["aliases"], {"blocks":"light.blocks"})
        self.assertEqual(context["services"], ({"domain":"light", "service":"turn_on", "fields":("brightness",)},))
