"""Registry of Jarvis capabilities and the providers that offer them."""

from __future__ import annotations

from collections.abc import Iterable

from jarvis.models.capability import (
    AvailableCapability,
    Capability,
    CapabilityName,
    CapabilityProvider,
)
from jarvis.models.request import RequestClassification, RequestType
from jarvis.models.request_context import RequestContext
from jarvis.models.request_state import RequestState


DEFAULT_CAPABILITIES: tuple[Capability, ...] = (
    Capability(
        CapabilityName.CONVERSATION,
        "Support natural conversation with Jarvis.",
        frozenset({RequestType.CONVERSATION}),
    ),
    Capability(
        CapabilityName.HOME_ASSISTANT,
        "Coordinate requests about the connected home.",
        frozenset({RequestType.COMMAND, RequestType.QUERY, RequestType.AUTOMATION}),
    ),
    Capability(
        CapabilityName.MEMORY,
        "Support requests concerning retained information.",
        frozenset({RequestType.MEMORY}),
    ),
    Capability(
        CapabilityName.KNOWLEDGE,
        "Provide home-specific knowledge.",
        frozenset({RequestType.INFORMATION, RequestType.QUERY}),
    ),
    Capability(
        CapabilityName.CALENDAR,
        "Support calendar-related requests.",
        frozenset({RequestType.QUERY, RequestType.PLANNING, RequestType.AUTOMATION}),
    ),
    Capability(
        CapabilityName.WEATHER,
        "Support weather-related requests.",
        frozenset({RequestType.INFORMATION, RequestType.QUERY}),
    ),
    Capability(
        CapabilityName.NOTIFICATIONS,
        "Support notification requests.",
        frozenset({RequestType.COMMAND, RequestType.AUTOMATION}),
    ),
    Capability(
        CapabilityName.SEARCH,
        "Support information-search requests.",
        frozenset({RequestType.INFORMATION, RequestType.QUERY}),
    ),
    Capability(
        CapabilityName.VISION,
        "Support requests involving visual input.",
        frozenset({RequestType.QUERY, RequestType.INFORMATION}),
    ),
    Capability(
        CapabilityName.REASONING,
        "Support requests that require planning or analysis.",
        frozenset({RequestType.PLANNING, RequestType.INFORMATION}),
    ),
)


class CapabilityRegistry:
    """Store capabilities and the available providers for each capability."""

    def __init__(self, capabilities: Iterable[Capability] = DEFAULT_CAPABILITIES) -> None:
        self._capabilities: dict[str, Capability] = {}
        self._providers: dict[str, dict[str, CapabilityProvider]] = {}

        for capability in capabilities:
            self.register_capability(capability)

    def register_capability(self, capability: Capability) -> None:
        """Add a capability to the catalog."""

        if capability.name in self._capabilities:
            raise ValueError(f"Capability already registered: {capability.name}")

        self._capabilities[capability.name] = capability
        self._providers[capability.name] = {}

    def register_provider(self, provider: CapabilityProvider) -> None:
        """Register a provider for an existing capability."""

        providers = self._providers.get(provider.capability_name)
        if providers is None:
            raise ValueError(f"Unknown capability: {provider.capability_name}")

        if provider.provider_id in providers:
            raise ValueError(
                "Provider already registered for capability: "
                f"{provider.capability_name}/{provider.provider_id}"
            )

        providers[provider.provider_id] = provider

    def get_capability(self, name: str) -> Capability | None:
        """Return a capability from the catalog by name."""

        return self._capabilities.get(name)

    def all_capabilities(self) -> tuple[Capability, ...]:
        """Return every registered capability in registration order."""

        return tuple(self._capabilities.values())

    def available_for(
        self,
        classification: RequestClassification,
    ) -> tuple[AvailableCapability, ...]:
        """Return available capabilities that are relevant to a request."""

        available_capabilities = []

        for capability in self._capabilities.values():
            if classification.request_type not in capability.request_types:
                continue

            providers = tuple(
                provider
                for provider in self._providers[capability.name].values()
                if provider.available
            )

            if providers:
                available_capabilities.append(
                    AvailableCapability(capability, providers)
                )

        return tuple(available_capabilities)

    def select_for(self, request_context: RequestContext) -> tuple[AvailableCapability, ...]:
        """Select available capabilities and enrich a request context."""

        try:
            capabilities = (
                self.available_for(request_context.classification)
                if request_context.classification is not None
                else ()
            )
        except Exception:
            request_context.state = RequestState.FAILED
            raise

        request_context.selected_capabilities = capabilities
        request_context.state = RequestState.CAPABILITIES_SELECTED
        return capabilities
