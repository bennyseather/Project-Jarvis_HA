"""
Project Jarvis

Main application class.
"""

import asyncio
import os
from datetime import datetime, timezone

from rich.console import Console
from rich.panel import Panel

from jarvis.core.assistant import Assistant
from jarvis.core.container import ServiceContainer
from jarvis.core.context_builder import ContextBuilder
from jarvis.homeassistant.client import HomeAssistantClient
from jarvis.homeassistant.entity_resolver import EntityResolver
from jarvis.providers.openai_provider import OpenAIProvider
from jarvis.core.assistant_factory import create_read_only_assistant
from jarvis.context.context_assembler import ContextAssembler
from jarvis.context.providers import MemoryContextProvider, KnowledgeContextProvider
from jarvis.memory.in_memory_store import InMemoryMemoryStore
from jarvis.memory.policy import ExplicitMemoryPolicy
from jarvis.memory.ranker import DeterministicMemoryRanker
from jarvis.memory.retriever import PolicyControlledMemoryRetriever
from jarvis.knowledge.in_memory_store import InMemoryKnowledgeStore
from jarvis.knowledge.policy import ExplicitKnowledgePolicy
from jarvis.knowledge.ranker import DeterministicKnowledgeRanker
from jarvis.knowledge.retriever import PolicyControlledKnowledgeRetriever
from jarvis.models.request import Request
from jarvis.models.request_context import RequestContext
from jarvis.homeassistant.capability_discovery import HomeAssistantCapabilityDiscovery
from jarvis.homeassistant.capability_gateway import HomeAssistantCapabilityGateway
from jarvis.homeassistant.risk_policy import HomeAssistantRiskPolicy
from jarvis.homeassistant.pending_actions import PendingActionStore
from jarvis.homeassistant.action_gateway import ConfirmedHomeAssistantActionGateway
from jarvis.homeassistant.entity_reference_resolver import EntityReferenceResolver
from jarvis.timeline.policy import EventTimelinePolicy
from jarvis.timeline.store import InMemoryTimelineStore
from jarvis.timeline.subscriber import HomeAssistantEventSubscriber
from jarvis.models.event_timeline import TimelineQuery
from jarvis.storage.sqlite_stores import SQLiteKnowledgeStore, SQLiteMemoryStore
from jarvis.storage.conversation_store import SQLiteConversationStore
from jarvis.memory.writer import PolicyControlledMemoryWriter
from jarvis.memory.manager import PolicyControlledMemoryManager
from jarvis.models.memory import MemoryRecordFactory
from jarvis.knowledge.writer import PolicyControlledKnowledgeWriter
from jarvis.models.knowledge import KnowledgeRecordFactory
from jarvis.management.console_commands import ExplicitDataConsole
from jarvis.homeassistant.capability_context import HomeAssistantCapabilityContext
from jarvis.homeassistant.enrollment import HomeAccessEnrollment
from jarvis.homeassistant.access_policy import resolve_device_services, resolve_entities
from jarvis.homeassistant.action_audit import SQLiteConfirmedActionAuditStore
from jarvis.homeassistant.home_references import build_home_references
from jarvis.memory.repeated_context import RepeatedContextExtractor, RepeatedContextLearner
from jarvis.management.natural_memory import NaturalMemoryController
from jarvis.persona import JarvisPersona
from jarvis.personality import PersonalityManager
from jarvis.reflection.manager import ReflectiveLearningManager
from jarvis.storage.reflection_store import SQLiteReflectionStore
from jarvis.proactive.controller import NaturalProactiveController
from jarvis.proactive.delivery import HomeAssistantProactiveDelivery
from jarvis.proactive.detector import ProactiveOpportunityDetector
from jarvis.proactive.manager import ProactiveAssistanceManager
from jarvis.proactive.policy import ProactiveAssistancePolicy
from jarvis.proactive.store import SQLiteProactiveStore
from jarvis.homeassistant.home_topology import HomeTopologyAssembler
from jarvis.homeassistant.situational_intelligence import (
    SituationalIntelligencePolicy,
    WholeHomeSituationalIntelligence,
)
from jarvis.homeassistant.compound_orchestration import (
    CompoundHomeOrchestrator,
    CompoundOrchestrationPolicy,
)
from jarvis.homeassistant.contextual_goals import ContextualGoalManager
from jarvis.research import GeneralResearchProvider, ResearchController, ResearchPolicy


class JarvisApplication:
    """
    Main application for Project Jarvis.
    """

    def __init__(self):
        """
        Create a new Jarvis application.
        """
        self.console = Console()
        self.container = ServiceContainer()
        self.general = None
        self.status = "Stopped"
        self.debug_mode = True
        self._pending_action_payloads: dict[
            str, tuple[str, dict[str, object]]
        ] = {}
        self._request_lock = asyncio.Lock()

    async def run(self):
        """
        Start Jarvis.
        """
        self.load_configuration()
        self.initialize_services()
        try:
            await self.connect_services()
            await self.startup_checks()
        except Exception:
            self.status = "Unavailable"
            self.container.logger.error("Startup checks failed; Home Assistant is unavailable.")
            self.console.print("[red]Jarvis could not start because Home Assistant is unavailable.[/red]")
            await self.container.home_assistant.disconnect()
            return

        self.status = "Running"

        self.show_banner()

        self.console.print("[green]✓ Jarvis started successfully[/green]")

        if self.debug_mode:
            self.console.print("[magenta]Debug mode is enabled[/magenta]")

            current_status = self.get_status()
            status_message = f"Current status: {current_status}"

            startup_steps = [
                "Configuration loaded",
                "Home Assistant connected",
                "OpenAI connected",
                "Conversation test completed",
                "Banner displayed",
                "Application running",
            ]

            self.console.print(f"[cyan]{status_message}[/cyan]")

            for step in startup_steps:
                self.console.print(f"[blue]Startup step: {step}[/blue]")

            project = self.general["project"]

            self.console.print(
                f"[green]Project name: {project['name']}[/green]"
            )

            self.console.print(
                f"[green]Project version: {project['version']}[/green]"
            )

        if self.get_status() == "Running":
            try:
                await self.keep_running()
            finally:
                if self.container.timeline_task is not None:
                    self.container.timeline_task.cancel()
                if self.container.proactive_task is not None:
                    self.container.proactive_task.cancel()
                if self.container.timeline_client is not None:
                    await self.container.timeline_client.disconnect()
                if self.container.proactive_client is not None:
                    await self.container.proactive_client.disconnect()
                await self.container.home_assistant.disconnect()
                self.container.memory_store.close()
                self.container.knowledge_store.close()
                self.container.conversation_store.close()
                self.container.reflection_store.close()
                self.container.proactive_store.close()
                self.container.confirmed_action_audit_store.close()
        else:
            self.console.print("[red]Jarvis is not running.[/red]")

    def load_configuration(self):
        """
        Load the application configuration.
        """
        self.general = self.container.config_loader.load()
        storage_path = os.environ.get("JARVIS_STORAGE_PATH")
        if storage_path:
            self.general.setdefault("storage", {})["database_path"] = storage_path

        self.container.logger.info("Configuration loaded")

        self.container.event_bus.publish("ApplicationStarted")

    def initialize_services(self):
        """
        Create shared services.
        """

        ha_config = self.general["home_assistant"]
        self._validate_home_assistant_policy(ha_config)
        storage_config = self.general.get("storage", {})
        database_path = storage_config.get("database_path", "data/jarvis.sqlite3")
        if not isinstance(database_path, str) or not database_path.strip():
            raise ValueError("storage.database_path must be a non-empty string")
        database_file = self.container.config_loader.project_root / database_path
        conversation_config = self.general.get("conversation", {})
        reflection_config = self.general.get("reflection", {})
        if not isinstance(reflection_config, dict):
            raise ValueError("reflection must be a mapping")
        reflection_context_limit = reflection_config.get("context_limit", 5)
        if (
            not isinstance(reflection_context_limit, int)
            or isinstance(reflection_context_limit, bool)
            or not 0 <= reflection_context_limit <= 10
        ):
            raise ValueError(
                "reflection.context_limit must be an integer between 0 and 10"
            )
        persona_config = self.general.get("persona", {})
        if not isinstance(persona_config, dict):
            raise ValueError("persona must be a mapping")
        persona_name = persona_config.get("name", "Jarvis")
        dry_wit = persona_config.get("dry_wit", True)
        if not isinstance(persona_name, str) or not persona_name.strip():
            raise ValueError("persona.name must be a non-empty string")
        if not isinstance(dry_wit, bool):
            raise ValueError("persona.dry_wit must be a boolean")
        persona = JarvisPersona(persona_name.strip(), dry_wit)
        context_messages = conversation_config.get("context_messages", 20)
        maximum_conversations = conversation_config.get("maximum_conversations", 20)
        retention_days = conversation_config.get("retention_days", 3)
        maximum_messages = conversation_config.get("maximum_messages_per_conversation", 100)
        for name, value, minimum, maximum in (
            ("context_messages", context_messages, 2, 50),
            ("maximum_conversations", maximum_conversations, 1, 100),
            ("retention_days", retention_days, 1, 30),
            ("maximum_messages_per_conversation", maximum_messages, 2, 500),
        ):
            if not isinstance(value, int) or isinstance(value, bool) or not minimum <= value <= maximum:
                raise ValueError(f"conversation.{name} must be an integer between {minimum} and {maximum}")
        if context_messages > maximum_messages:
            raise ValueError("conversation.context_messages cannot exceed maximum_messages_per_conversation")

        self.container.home_assistant = HomeAssistantClient(
            url=ha_config["url"],
            token=ha_config["token"],
            logger=self.container.logger,
        )

        self.container.openai = OpenAIProvider(
            api_key=self.general["openai"]["api_key"],
            logger=self.container.logger,
        )

        self.container.context_builder = ContextBuilder()
        clock = lambda: datetime.now(timezone.utc)
        self.container.memory_store = SQLiteMemoryStore(database_file)
        self.container.knowledge_store = SQLiteKnowledgeStore(database_file)
        self.container.conversation_store = SQLiteConversationStore(
            database_file,
            maximum_conversations=maximum_conversations,
            retention_days=retention_days,
            maximum_messages=maximum_messages,
        )
        self.container.reflection_store = SQLiteReflectionStore(database_file)
        self.container.reflective_learning_manager = ReflectiveLearningManager(
            self.container.memory_store,
            self.container.reflection_store,
            clock,
        )
        self.container.reflection_context_limit = reflection_context_limit
        self.container.proactive_policy = ProactiveAssistancePolicy.from_config(
            self.general.get("proactive", {})
        )
        self.container.research_policy = ResearchPolicy.from_config(
            self.general.get("research", {})
        )
        self.container.proactive_store = SQLiteProactiveStore(database_file)
        self.container.proactive_manager = ProactiveAssistanceManager(
            self.container.proactive_store,
            self.container.proactive_policy,
            ProactiveOpportunityDetector(
                low_battery_threshold=(
                    self.container.proactive_policy.low_battery_threshold
                ),
                routine_repeat_threshold=(
                    self.container.proactive_policy.routine_repeat_threshold
                ),
            ),
            clock=clock,
        )
        self.container.proactive_controller = NaturalProactiveController(
            self.container.proactive_manager
        )
        self.container.proactive_delivery = HomeAssistantProactiveDelivery(
            self.container.proactive_manager,
            self.container.proactive_policy,
            clock,
        )
        self.container.situational_policy = (
            SituationalIntelligencePolicy.from_config(
                self.general.get("situational_intelligence", {})
            )
        )
        self.container.compound_orchestration_policy = (
            CompoundOrchestrationPolicy.from_config(
                self.general.get("compound_orchestration", {})
            )
        )
        self.container.conversation_context_messages = context_messages
        self.container.confirmed_action_audit_store = SQLiteConfirmedActionAuditStore(database_file)
        self.container.runtime_context_assembler = ContextAssembler((
            MemoryContextProvider(PolicyControlledMemoryRetriever(
                self.container.memory_store, ExplicitMemoryPolicy(),
                DeterministicMemoryRanker(), lambda: datetime.now(timezone.utc),
            )),
            KnowledgeContextProvider(PolicyControlledKnowledgeRetriever(
                self.container.knowledge_store, ExplicitKnowledgePolicy(),
                DeterministicKnowledgeRanker(),
            )),
        ))
        self.container.memory_writer = PolicyControlledMemoryWriter(
            self.container.memory_store, ExplicitMemoryPolicy(), MemoryRecordFactory(timestamp_factory=clock), clock
        )
        self.container.memory_manager = PolicyControlledMemoryManager(
            self.container.memory_store, ExplicitMemoryPolicy()
        )
        self.container.knowledge_writer = PolicyControlledKnowledgeWriter(
            self.container.knowledge_store, ExplicitKnowledgePolicy(), KnowledgeRecordFactory(timestamp_factory=clock), clock
        )
        self.container.explicit_data_console = ExplicitDataConsole(
            self.container.memory_writer, self.container.memory_manager,
            self.container.knowledge_writer, self.container.knowledge_store,
        )
        self.container.repeated_context_learner = RepeatedContextLearner(
            self.container.conversation_store,
            self.container.memory_store,
            self.container.memory_writer,
            RepeatedContextExtractor(self.container.openai),
            self.container.reflective_learning_manager,
        )
        self.container.natural_memory_controller = NaturalMemoryController(
            self.container.memory_store,
            self.container.memory_writer,
            self.container.conversation_store,
            self.container.repeated_context_learner,
            self.container.reflective_learning_manager,
        )
        self.container.research_provider = GeneralResearchProvider(
            self.container.openai,
            self.container.research_policy,
        )
        self.container.research_controller = ResearchController(
            self.container.research_policy,
            self.container.memory_store,
            self.container.memory_writer,
        )
        self.container.reflective_learning_manager.refresh()

        self.container.assistant = Assistant(
            openai=self.container.openai,
            context_builder=self.container.context_builder,
        )

        self.container.entity_resolver = EntityResolver(
            self.container.entity_registry
        )
        allowed_read_entities = frozenset(
            ha_config.get("allowed_read_entities", ())
        )
        resolver = EntityReferenceResolver(
            allowed_read_entities | frozenset(ha_config.get("action_policy", {}).get("allowed_entities", ())),
            ha_config.get("entity_aliases", {}),
        )
        self.container.read_only_assistant = create_read_only_assistant(
            self.container.openai,
            self.container.home_assistant,
            allowed_read_entities,
            resolver,
            persona,
            self.container.research_provider,
        )
        timeline_config = self.general.get("event_timeline", {})
        self._validate_timeline_config(timeline_config)
        self.container.timeline_store = InMemoryTimelineStore(timeline_config.get("max_events", 50))
        self.container.timeline_policy = EventTimelinePolicy(
            timeline_config.get("enabled", False),
            timeline_config.get("allowed_event_types", ()),
            timeline_config.get("allowed_entities", ()),
        )


    async def connect_services(self):
        """
        Connect external services.
        """

        entities = await self.container.home_assistant.connect()

        self.container.entity_registry.load(entities)

        catalog = await HomeAssistantCapabilityDiscovery(
            self.container.home_assistant
        ).discover()
        try:
            areas = await self.container.home_assistant.get_registry("config/area_registry/list")
            display = await self.container.home_assistant.get_registry("config/entity_registry/list_for_display")
            registry = display.get("entities", ())
            devices = await self.container.home_assistant.get_registry("config/device_registry/list")
        except Exception:
            areas, registry, devices = [], [], []
        try:
            floors = await self.container.home_assistant.get_registry(
                "config/floor_registry/list"
            )
        except Exception:
            floors = []
        action_config = self.general.get("home_assistant", {}).get("action_policy", {})
        ha_config = self.general["home_assistant"]
        allowed_reads = resolve_entities(
            catalog, ha_config.get("allowed_read_entities", ()), ha_config.get("allowed_read_domains", ()),
            ha_config.get("excluded_entities", ()), all_entities=ha_config.get("all_entities", False),
        )
        allowed_actions = resolve_entities(
            catalog, action_config.get("allowed_entities", ()), action_config.get("allowed_domains", ()),
            tuple(ha_config.get("excluded_entities", ())) + tuple(action_config.get("excluded_entities", ())),
            all_entities=action_config.get("all_entities", False),
        )
        allowed_services = resolve_device_services(
            catalog, action_config.get("all_device_services", False),
            tuple(action_config.get("confirm_required", ())) + tuple(action_config.get("high_impact", ())),
        )
        permitted = allowed_reads | allowed_actions
        names, area_members, groups = build_home_references(
            entities, areas, registry, devices, permitted
        )
        self.container.home_topology_assembler = HomeTopologyAssembler(
            areas,
            floors,
            registry,
            devices,
            allowed_reads,
            allowed_actions,
            groups,
            maximum_entities=(
                self.container.situational_policy.maximum_entities
            ),
        )
        floor_members = self.container.home_topology_assembler.floor_references
        self.container.read_only_assistant._allowed_entity_ids = allowed_reads
        self.container.read_only_assistant._resolver = EntityReferenceResolver(
            permitted,
            ha_config.get("entity_aliases", {}),
            names,
            area_members,
            groups,
            floor_members,
        )
        self.container.home_assistant_capability_context = HomeAssistantCapabilityContext(
            catalog,
            allowed_reads,
            allowed_actions,
            allowed_services,
            self.general["home_assistant"].get("entity_aliases", {}),
        )
        self.container.home_reference_context = {
            "friendly_names": tuple(sorted(names)[:500]),
            "areas": tuple(sorted(area_members)[:100]),
            "groups": tuple(sorted(groups)[:100]),
            "floors": tuple(sorted(floor_members)[:50]),
        }
        self.container.home_access_enrollment = HomeAccessEnrollment(
            os.environ.get("JARVIS_HOME_POLICY_PATH", str(self.container.config_loader.config_folder / "general.yaml")), catalog
        )
        self.container.home_assistant_action_gateway = ConfirmedHomeAssistantActionGateway(
            HomeAssistantCapabilityGateway(catalog),
            HomeAssistantRiskPolicy(
                action_config.get("confirm_required", ()),
                action_config.get("high_impact", ()),
                allowed_actions,
                allowed_services,
            ),
            PendingActionStore(),
            self.container.home_assistant,
            self.container.confirmed_action_audit_store,
        )
        self.container.read_only_assistant.set_action_gateway(
            self.container.home_assistant_action_gateway
        )
        self.container.proactive_manager.set_action_gateway(
            self.container.home_assistant_action_gateway
        )
        self.container.situational_intelligence = (
            WholeHomeSituationalIntelligence(
                self.container.home_assistant,
                self.container.home_topology_assembler,
                self.container.timeline_store,
                self.container.home_assistant_action_gateway,
                self.container.situational_policy,
            )
        )
        self.container.compound_orchestration = CompoundHomeOrchestrator(
            self.container.home_assistant,
            self.container.home_topology_assembler,
            self.container.home_assistant_action_gateway,
            self.container.compound_orchestration_policy,
        )
        self.container.contextual_goals = ContextualGoalManager(
            self.container.knowledge_store,
            self.container.compound_orchestration,
        )
        self.container.personality_manager = PersonalityManager(
            self.container.knowledge_store
        )
        self.container.proactive_allowed_entities = allowed_reads
        timeline_config = self.general.get("event_timeline", {})
        if (
            self.container.timeline_policy.enabled
            and not timeline_config.get("allowed_entities")
        ):
            self.container.timeline_policy.authorize_permitted_entities(
                allowed_reads
            )
        if self.container.timeline_policy.enabled:
            ha_config = self.general["home_assistant"]
            self.container.timeline_client = HomeAssistantClient(
                ha_config["url"], ha_config["token"], self.container.logger
            )
            self.container.timeline_subscriber = HomeAssistantEventSubscriber(
                self.container.timeline_client,
                self.container.timeline_policy,
                self.container.timeline_store,
            )
            self.container.timeline_task = asyncio.create_task(
                self.container.timeline_subscriber.run()
            )
        if self.container.proactive_policy.enabled:
            self.container.proactive_client = HomeAssistantClient(
                ha_config["url"], ha_config["token"], self.container.logger
            )
            self.container.proactive_task = asyncio.create_task(
                self._run_proactive_loop()
            )

        self.container.logger.info(
            f"Loaded {self.container.entity_registry.count()} entities into registry."
        )
        self.container.logger.info(
            f"Home policy ready: {len(allowed_reads)} read entities, {len(allowed_actions)} action entities."
        )

    async def startup_checks(self):
        """
        Run startup verification checks.
        """

        capabilities = self.container.home_assistant_capability_context.as_context()
        self.container.logger.info(
            f"Home Assistant ready with {self.container.entity_registry.count()} discovered entities, "
            f"{len(capabilities['read_entities'])} effective allowed reads, and "
            f"{len(capabilities['action_entities'])} effective allowed action entities."
        )
        self.container.logger.info(
            "Home policy source is the configured durable policy file; bridge runtime is ready."
        )

        self.container.logger.info("Provider startup checks are connectivity-only.")

    async def handle_request(
        self,
        text: str,
        conversation_id: str | None = None,
        *,
        voice_mode: bool = False,
        source_id: str | None = None,
    ) -> dict[str, object]:
        """Route one user request through the configured safe assistant slice."""

        async with self._request_lock:
            return await self._handle_request(
                text, conversation_id, voice_mode, source_id
            )

    async def _handle_request(
        self,
        text: str,
        conversation_id: str | None,
        voice_mode: bool,
        source_id: str | None,
    ) -> dict[str, object]:
        conversation_store = self.container.conversation_store
        identifier = conversation_store.normalize_conversation_id(conversation_id)
        user_message = conversation_store.add_message(identifier, "user", text)
        self.container.read_only_assistant.activate_conversation(identifier)

        personality_result = self.container.personality_manager.handle(text)
        if personality_result is not None:
            conversation_store.add_message(
                identifier, "assistant", self._user_message(personality_result)
            )
            return personality_result
        research_control = self.container.research_controller.handle(text, identifier)
        if research_control is not None:
            conversation_store.add_message(
                identifier, "assistant", self._user_message(research_control)
            )
            return research_control
        goal_management = self.container.contextual_goals.manage(text, identifier)
        if goal_management is not None:
            conversation_store.add_message(
                identifier, "assistant", self._user_message(goal_management)
            )
            return goal_management
        natural_result = self.container.natural_memory_controller.handle(text, identifier)
        if natural_result is not None:
            conversation_store.add_message(identifier, "assistant", self._user_message(natural_result))
            return natural_result
        home_result = self._handle_home_access_command(text)
        if home_result is not None:
            conversation_store.add_message(identifier, "assistant", self._user_message(home_result))
            return home_result
        management_result = self.container.explicit_data_console.handle(text)
        if management_result is not None:
            conversation_store.add_message(identifier, "assistant", self._user_message(management_result))
            return management_result
        self._refresh_proactive()
        proactive_result = await self.container.proactive_controller.handle(
            text, identifier
        )
        if proactive_result is not None:
            conversation_store.add_message(
                identifier, "assistant", self._user_message(proactive_result)
            )
            return proactive_result
        goal_result = await self.container.contextual_goals.handle(
            text, identifier
        )
        if goal_result is not None:
            conversation_store.add_message(
                identifier, "assistant", self._user_message(goal_result)
            )
            return goal_result
        compound_result = await self.container.compound_orchestration.handle(
            text, identifier
        )
        if compound_result is not None:
            conversation_store.add_message(
                identifier,
                "assistant",
                self._user_message(compound_result),
            )
            return compound_result
        situational_result = await self.container.situational_intelligence.handle(
            text,
            identifier,
            voice_mode=voice_mode,
            source_id=source_id,
        )
        if situational_result is not None:
            conversation_store.add_message(
                identifier,
                "assistant",
                self._user_message(situational_result),
            )
            return situational_result
        if not hasattr(self.container, "read_only_assistant"):
            return {"status": "not_supported", "message": "Assistant runtime is unavailable."}
        promotion_result = self.container.repeated_context_learner.observe(user_message)
        if promotion_result is not None:
            conversation_store.add_message(identifier, "assistant", self._user_message(promotion_result))
            return promotion_result
        request_context = RequestContext(Request(text))
        self.container.reflective_learning_manager.refresh()
        package = self.container.runtime_context_assembler.assemble(request_context)
        history = conversation_store.history(
            identifier,
            self.container.conversation_context_messages,
        )
        context = {
            "memory": self._context_items(package.memory),
            "knowledge": self._context_items(package.knowledge),
            "conversation": tuple(message.to_openai() for message in history[:-1]),
            "conversation_id": identifier,
            "interaction": {"voice": voice_mode},
            "personality": self.container.personality_manager.profile().context(),
            "research": self.container.research_policy.context(
                self.container.research_controller.enabled(identifier)
            ),
            "reflection": self.container.reflective_learning_manager.context_for(
                text, self.container.reflection_context_limit
            ),
            "proactive": self.container.proactive_manager.context_for(text),
            "home_assistant": self.container.home_assistant_capability_context.as_context(),
        }
        context["home_assistant"]["references"] = self.container.home_reference_context
        context["home_assistant"]["situational"] = (
            self.container.situational_intelligence.context(identifier)
        )
        result = await self.container.read_only_assistant.handle(text, context)
        if result.get("sources") and not voice_mode:
            result = dict(result)
            result["message"] = (
                str(result.get("message", "")).rstrip()
                + "\n\nSources:\n"
                + "\n".join(
                    f"- {source['title']} — {source['url']}"
                    for source in result["sources"]
                )
            )
        self.container.research_controller.record(identifier, result)
        message = self._user_message(result)
        if message:
            conversation_store.add_message(identifier, "assistant", message)
        return result

    def _refresh_proactive(self, states=None) -> None:
        """Refresh bounded suggestions from permitted runtime inputs."""
        if not self.container.proactive_policy.enabled:
            return
        available = (
            self.container.entity_registry.all()
            if states is None
            else states
        )
        permitted = tuple(
            state for state in available
            if (
                state.get("entity_id") if isinstance(state, dict)
                else getattr(state, "entity_id", None)
            ) in self.container.proactive_allowed_entities
        )
        events = self.container.timeline_store.retrieve(
            TimelineQuery(maximum_results=50)
        )
        self.container.proactive_manager.refresh(
            states=permitted,
            timeline_events=events,
            reflections=self.container.reflective_learning_manager.records(),
        )

    async def _run_proactive_loop(self) -> None:
        """Periodically evaluate and deliver bounded Home Assistant suggestions."""
        client = self.container.proactive_client
        try:
            states = await client.connect()
            while True:
                self._refresh_proactive(states)
                try:
                    await self.container.proactive_delivery.deliver(client)
                except Exception as error:
                    self.container.logger.warning(
                        f"Proactive delivery failed safely: {error}"
                    )
                await asyncio.sleep(
                    self.container.proactive_policy.scan_interval_seconds
                )
                states = await client.get_states()
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self.container.logger.error(
                f"Proactive assistance stopped safely: {error}"
            )

    @staticmethod
    def _user_message(result: dict[str, object]) -> str:
        """Return a stable, safe console response for every runtime outcome."""
        messages = {
            "success": "Action completed." if "message" not in result else str(result["message"]),
            "clarification_required": str(result.get(
                "message", "Please specify the exact configured entity you mean."
            )),
            "not_supported": "That request is not available in the current configuration.",
            "unavailable": "The requested service is temporarily unavailable. Please try again.",
            "forbidden": "That confirmation is invalid or has expired." if result.get("reason_code") == "invalid_confirmation" else "That action is not authorized.",
            "requires_confirmation": "Confirmation is required before this action can run.",
        }
        return messages.get(str(result.get("status")), str(result.get("message", "Request could not be completed.")))

    @staticmethod
    def _context_items(section) -> tuple[dict[str, object], ...]:
        if section is None:
            return ()
        return tuple(
            {
                "content": match.content,
                "title": getattr(match, "title", None),
                "type": str(getattr(match, "memory_type", getattr(match, "knowledge_type", ""))),
                "tags": match.tags,
                "score": match.retrieval_score,
            }
            for match in section.matches
        )

    async def keep_running(self):
        """Run the first minimal interactive request loop."""

        self.console.print("[green]Jarvis is ready. Type 'quit' to exit.[/green]")
        while True:
            text = await asyncio.to_thread(input, "You: ")
            if text.strip().casefold() in {"quit", "exit"}:
                return
            if not text.strip():
                continue
            enrollment_result = self._handle_home_access_command(text)
            if enrollment_result is not None:
                self.console.print(f"Jarvis [{enrollment_result['status']}]: {enrollment_result.get('message', '')}")
                if enrollment_result.get("entities"):
                    self.console.print("Entities: " + ", ".join(enrollment_result["entities"]))
                if enrollment_result.get("services"):
                    self.console.print("Services: " + ", ".join(enrollment_result["services"]))
                continue
            management_result = self.container.explicit_data_console.handle(text)
            if management_result is not None:
                self.console.print(f"Jarvis [{management_result['status']}]: {management_result['message']}")
                if management_result.get("id"):
                    self.console.print(f"ID: {management_result['id']}")
                if management_result.get("token"):
                    command = management_result.get("confirmation_command", "memory confirm")
                    self.console.print(f"Confirm: {command} {management_result['token']}")
                continue
            if text.strip().casefold().startswith("timeline"):
                parts = text.strip().split(maxsplit=1)
                entity_id = parts[1] if len(parts) == 2 else None
                events = self.container.timeline_store.retrieve(TimelineQuery(entity_id=entity_id))
                if not events:
                    self.console.print("Jarvis [success]: No configured recent events are available.")
                else:
                    for event in events:
                        state = "" if event.state is None else f" → {event.state}"
                        self.console.print(f"{event.occurred_at.isoformat()} {event.entity_id}{state}")
                continue
            if text.strip().startswith("confirm "):
                token = text.strip().split(maxsplit=1)[1]
                pending = self._pending_action_payloads.pop(token, None)
                payload = None if pending is None else pending[1]
                try:
                    if payload is None:
                        result = {
                            "status": "forbidden",
                            "message": "Confirmation is invalid.",
                        }
                    elif payload.get("kind") == "compound_plan":
                        result = await self.container.compound_orchestration.confirm(
                            token, payload
                        )
                    else:
                        result = await self.container.read_only_assistant.confirm_action(
                            token, payload
                        )
                except Exception:
                    result = {"status": "unavailable"}
                message = self._user_message(result)
                self.container.conversation_store.add_message("local-default", "assistant", message)
                self.console.print(f"Jarvis [{result['status']}]: {message}")
                continue
            result = await self.handle_request(text)
            if result.get("status") == "requires_confirmation":
                token = result.get("token")
                payload = result.pop("action_payload", None)
                if token and payload:
                    self._pending_action_payloads[token] = ("local-default", payload)
                    self.console.print(f"Confirm action: {result.get('summary', '')}. Type: confirm {token}")
                    continue
            self.console.print(f"Jarvis [{result['status']}]: {self._user_message(result)}")

    def _handle_home_access_command(self, text: str) -> dict[str, object] | None:
        """Handle explicit enrollment commands before the model request path."""
        parts = text.strip().split()
        if not parts or parts[0] != "home":
            return None
        enrollment = self.container.home_access_enrollment
        if len(parts) in {2, 3} and parts[1] == "discover":
            return enrollment.discover(parts[2] if len(parts) == 3 else None)
        if len(parts) == 4 and parts[1:3] == ["enroll", "read"]:
            return enrollment.enroll_read(parts[3])
        if len(parts) in {5, 6} and parts[1:3] == ["enroll", "action"]:
            return enrollment.enroll_action(parts[3], parts[4], parts[5] if len(parts) == 6 else "normal")
        if len(parts) == 4 and parts[1] == "alias":
            return enrollment.set_alias(parts[2], parts[3])
        if len(parts) == 2 and parts[1] == "review": return enrollment.review()
        if len(parts) == 3 and parts[1] == "exclude": return enrollment.exclude(parts[2])
        if len(parts) in {2, 3} and parts[1] == "audit":
            try:
                limit = 10 if len(parts) == 2 else int(parts[2])
                records = self.container.confirmed_action_audit_store.recent(limit)
            except ValueError:
                return {"status": "not_supported", "message": "Use: home audit [1-50]."}
            if not records:
                return {"status": "success", "message": "No device actions have been recorded."}
            entries = "; ".join(
                f"{record.occurred_at.isoformat(timespec='seconds')} {record.domain}.{record.service} "
                f"{', '.join(record.entity_ids)}: {record.outcome}"
                for record in records
            )
            return {"status": "success", "message": f"Recent device actions: {entries}"}
        return {"status":"not_supported","message":"Use: home discover [domain], home enroll read <entity>, home enroll action <entity> <service> [normal|high], home alias <name> <entity>, home review, home exclude <entity>, or home audit [1-50]."}

    def show_banner(self):
        """
        Display the startup banner.
        """

        title = (
            f"[bold cyan]{self.general['project']['name']}[/bold cyan]\n"
            "[white]AI-powered Home Assistant Companion[/white]"
        )

        panel = Panel(
            title,
            expand=False,
            border_style="cyan",
        )

        self.console.print()
        self.console.print(panel)
        self.console.print()

        self.console.print(
            f"[green]Version : {self.general['project']['version']}[/green]"
        )

        self.console.print(
            f"[yellow]Status  : {self.status}[/yellow]"
        )

        self.console.print()

    def say_goodbye(self, message):
        """
        Display a shutdown message.
        """

        self.console.print(f"[blue]{message}[/blue]")

    def get_status(self):
        """
        Return the current application status.
        """

        return self.status

    @staticmethod
    def _validate_home_assistant_policy(config: dict) -> None:
        """Reject malformed read/action authorization configuration at startup."""
        policy = config.get("action_policy", {})
        for name, values in {
            "allowed_read_entities": config.get("allowed_read_entities", ()),
            "allowed_read_domains": config.get("allowed_read_domains", ()),
            "excluded_entities": config.get("excluded_entities", ()),
            "confirm_required": policy.get("confirm_required", ()),
            "high_impact": policy.get("high_impact", ()),
            "allowed_entities": policy.get("allowed_entities", ()),
            "allowed_domains": policy.get("allowed_domains", ()),
            "action_excluded_entities": policy.get("excluded_entities", ()),
        }.items():
            if not isinstance(values, (list, tuple)) or any(
                not isinstance(value, str) or not value.strip() for value in values
            ):
                raise ValueError(f"home_assistant.{name} must be a list of non-empty strings.")
        for name, value in {
            "all_entities": config.get("all_entities", False),
            "action_policy.all_entities": policy.get("all_entities", False),
            "action_policy.all_device_services": policy.get("all_device_services", False),
        }.items():
            if not isinstance(value, bool):
                raise ValueError(f"home_assistant.{name} must be a boolean.")
        aliases = config.get("entity_aliases", {})
        if not isinstance(aliases, dict) or any(
            not isinstance(alias, str) or not alias.strip() or not isinstance(entity, str) or not entity.strip()
            for alias, entity in aliases.items()
        ):
            raise ValueError("home_assistant.entity_aliases must map non-empty strings to non-empty strings.")

    @staticmethod
    def _validate_timeline_config(config: dict) -> None:
        if not isinstance(config, dict) or not isinstance(config.get("enabled", False), bool):
            raise ValueError("event_timeline.enabled must be a boolean")
        for name in ("allowed_event_types", "allowed_entities"):
            values = config.get(name, ())
            if not isinstance(values, (list, tuple)) or any(not isinstance(value, str) or not value.strip() for value in values):
                raise ValueError(f"event_timeline.{name} must be a list of non-empty strings.")
        max_events = config.get("max_events", 50)
        if not isinstance(max_events, int) or isinstance(max_events, bool) or not 1 <= max_events <= 500:
            raise ValueError("event_timeline.max_events must be an integer between 1 and 500")
