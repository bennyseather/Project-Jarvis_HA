"""
Service container for Project Jarvis.
"""

from jarvis.capabilities.capability_registry import CapabilityRegistry
from jarvis.core.assistant import Assistant
from jarvis.core.config_loader import ConfigLoader
from jarvis.core.context_builder import ContextBuilder
from jarvis.core.event_bus import EventBus
from jarvis.core.logger import JarvisLogger
from jarvis.homeassistant.client import HomeAssistantClient
from jarvis.homeassistant.entity_registry import EntityRegistry
from jarvis.homeassistant.entity_resolver import EntityResolver
from jarvis.providers.openai_provider import OpenAIProvider


class ServiceContainer:
    """
    Holds shared services used throughout the application.
    """

    def __init__(self):
        self.logger = JarvisLogger()
        self.config_loader = ConfigLoader()
        self.event_bus = EventBus()

        self.entity_registry = EntityRegistry()

        self.capabilities = CapabilityRegistry()

        self.home_assistant: HomeAssistantClient | None = None
        self.openai: OpenAIProvider | None = None

        self.context_builder: ContextBuilder | None = None
        self.assistant: Assistant | None = None
        self.entity_resolver: EntityResolver | None = None