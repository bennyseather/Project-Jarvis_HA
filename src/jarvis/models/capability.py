"""Models that describe Jarvis capabilities and their providers."""

from __future__ import annotations

from dataclasses import dataclass

from jarvis.models.request import RequestType


class CapabilityName:
    """Names of the initial capabilities in the Jarvis capability catalog."""

    CONVERSATION = "conversation"
    HOME_ASSISTANT = "home_assistant"
    MEMORY = "memory"
    KNOWLEDGE = "knowledge"
    CALENDAR = "calendar"
    WEATHER = "weather"
    NOTIFICATIONS = "notifications"
    SEARCH = "search"
    VISION = "vision"
    REASONING = "reasoning"


@dataclass(frozen=True, slots=True)
class Capability:
    """A user-facing function Jarvis can offer."""

    name: str
    description: str
    request_types: frozenset[RequestType]


@dataclass(frozen=True, slots=True)
class CapabilityProvider:
    """A provider that makes one capability available to Jarvis."""

    capability_name: str
    provider_id: str
    available: bool = True


@dataclass(frozen=True, slots=True)
class AvailableCapability:
    """A capability and its currently available providers."""

    capability: Capability
    providers: tuple[CapabilityProvider, ...]
