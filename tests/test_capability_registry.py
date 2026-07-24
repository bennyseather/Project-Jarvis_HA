"""Unit tests for the capability registry."""

import unittest

from jarvis.capabilities.capability_registry import CapabilityRegistry
from jarvis.models.capability import Capability, CapabilityName, CapabilityProvider
from jarvis.models.request import Request, RequestClassification, RequestType


class CapabilityRegistryTests(unittest.TestCase):
    """Verify the catalog and provider-registration behavior."""

    def setUp(self) -> None:
        self.registry = CapabilityRegistry()

    def test_contains_the_initial_capability_catalog(self) -> None:
        capability_names = {
            capability.name for capability in self.registry.all_capabilities()
        }

        self.assertEqual(
            capability_names,
            {
                CapabilityName.CONVERSATION,
                CapabilityName.HOME_ASSISTANT,
                CapabilityName.MEMORY,
                CapabilityName.KNOWLEDGE,
                CapabilityName.CALENDAR,
                CapabilityName.WEATHER,
                CapabilityName.NOTIFICATIONS,
                CapabilityName.SEARCH,
                CapabilityName.VISION,
                CapabilityName.REASONING,
            },
        )

    def test_returns_multiple_available_providers_for_a_capability(self) -> None:
        self.registry.register_provider(
            CapabilityProvider(CapabilityName.HOME_ASSISTANT, "primary")
        )
        self.registry.register_provider(
            CapabilityProvider(CapabilityName.HOME_ASSISTANT, "fallback")
        )

        available = self.registry.available_for(self._classification(RequestType.COMMAND))

        self.assertEqual(len(available), 1)
        self.assertEqual(available[0].capability.name, CapabilityName.HOME_ASSISTANT)
        self.assertEqual(
            [provider.provider_id for provider in available[0].providers],
            ["primary", "fallback"],
        )

    def test_excludes_unavailable_providers(self) -> None:
        self.registry.register_provider(
            CapabilityProvider(
                CapabilityName.MEMORY,
                "memory-store",
                available=False,
            )
        )

        available = self.registry.available_for(self._classification(RequestType.MEMORY))

        self.assertEqual(available, ())

    def test_returns_empty_when_no_capability_is_available(self) -> None:
        available = self.registry.available_for(self._classification(RequestType.UNKNOWN))

        self.assertEqual(available, ())

    def test_accepts_plugin_capabilities(self) -> None:
        capability = Capability(
            "energy",
            "Support home energy requests.",
            frozenset({RequestType.QUERY}),
        )

        self.registry.register_capability(capability)
        self.registry.register_provider(CapabilityProvider("energy", "energy-plugin"))

        available = self.registry.available_for(self._classification(RequestType.QUERY))

        self.assertIn("energy", [item.capability.name for item in available])

    def test_rejects_a_provider_for_an_unknown_capability(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown capability"):
            self.registry.register_provider(CapabilityProvider("unknown", "plugin"))

    @staticmethod
    def _classification(request_type: RequestType) -> RequestClassification:
        return RequestClassification(Request("Test request"), request_type)
