import unittest

from jarvis.homeassistant.access_policy import resolve_device_services, resolve_entities
from jarvis.homeassistant.risk_policy import HomeAssistantRiskPolicy
from jarvis.models.home_assistant_gateway import (
    HomeAssistantActionProposal, HomeAssistantCapabilityCatalog, HomeAssistantRisk,
    HomeAssistantServiceDefinition,
)


class ImmediateAllDeviceControlTests(unittest.TestCase):
    def setUp(self):
        self.catalog = HomeAssistantCapabilityCatalog(
            (
                HomeAssistantServiceDefinition("light", "turn_on"),
                HomeAssistantServiceDefinition("lock", "unlock"),
                HomeAssistantServiceDefinition("automation", "turn_on"),
                HomeAssistantServiceDefinition("homeassistant", "turn_on"),
            ),
            frozenset({"light.blocks", "lock.front_door", "automation.arrive_home"}),
        )

    def test_all_entities_includes_priorly_protected_domains_but_preserves_exclusions(self):
        allowed = resolve_entities(self.catalog, excluded_entities=("automation.arrive_home",), all_entities=True)
        self.assertEqual(allowed, frozenset({"light.blocks", "lock.front_door"}))

    def test_all_device_services_excludes_control_plane_domains(self):
        services = resolve_device_services(self.catalog, all_device_services=True)
        self.assertEqual(services, frozenset({"light.turn_on", "lock.unlock"}))

    def test_immediate_policy_requires_a_matching_device_entity_and_service(self):
        policy = HomeAssistantRiskPolicy(
            allowed_entities={"light.blocks", "lock.front_door"},
            immediate_services={"light.turn_on", "lock.unlock"},
        )
        self.assertEqual(
            policy.evaluate(HomeAssistantActionProposal("light", "turn_on", ("light.blocks",))).risk,
            HomeAssistantRisk.IMMEDIATE,
        )
        self.assertEqual(
            policy.evaluate(HomeAssistantActionProposal("light", "turn_on", ("lock.front_door",))).risk,
            HomeAssistantRisk.FORBIDDEN,
        )
