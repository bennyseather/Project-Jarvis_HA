"""
Service container for Project Jarvis.
"""

from jarvis.capabilities.capability_registry import CapabilityRegistry
from jarvis.core.assistant import Assistant
from jarvis.core.config_loader import ConfigLoader
from jarvis.core.context_builder import ContextBuilder
from jarvis.core.conversation import Conversation
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
        self.conversation: Conversation | None = None
        self.conversation_store = None
        self.repeated_context_learner = None
        self.natural_memory_controller = None
        self.reflection_store = None
        self.reflective_learning_manager = None
        self.reflection_context_limit = 5
        self.read_only_assistant = None
        self.runtime_context_assembler = None
        self.home_assistant_action_gateway = None
        self.timeline_store = None
        self.timeline_subscriber = None
        self.timeline_client = None
        self.timeline_task = None
        self.home_assistant_capability_context = None
        self.home_access_enrollment = None
        self.confirmed_action_audit_store = None
        self.proactive_store = None
        self.proactive_policy = None
        self.proactive_manager = None
        self.proactive_controller = None
        self.proactive_delivery = None
        self.proactive_client = None
        self.proactive_task = None
        self.proactive_allowed_entities = frozenset()
        self.home_topology_assembler = None
        self.situational_policy = None
        self.situational_intelligence = None
        self.compound_orchestration_policy = None
        self.compound_orchestration = None
        self.stewardship_policy = None
        self.stewardship_store = None
        self.stewardship = None
        self.stewardship_task = None
        self.blueprint_planner = None
        self.contextual_goals = None
        self.personality_manager = None
        self.personality_presenter = None
        self.default_personality = None
        self.episodic_policy = None
        self.episodic_manager = None
        self.research_policy = None
        self.research_provider = None
        self.research_controller = None
        self.ai_budget_policy = None
        self.ai_usage_ledger = None
        self.hybrid_research_policy = None
        self.searxng_research = None
        self.entity_resolver: EntityResolver | None = None
