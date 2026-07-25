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
from jarvis.core.conversation import Conversation
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
from jarvis.memory.writer import PolicyControlledMemoryWriter
from jarvis.memory.manager import PolicyControlledMemoryManager
from jarvis.models.memory import MemoryRecordFactory
from jarvis.knowledge.writer import PolicyControlledKnowledgeWriter
from jarvis.models.knowledge import KnowledgeRecordFactory
from jarvis.management.console_commands import ExplicitDataConsole
from jarvis.homeassistant.capability_context import HomeAssistantCapabilityContext
from jarvis.homeassistant.enrollment import HomeAccessEnrollment


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
        self._pending_action_payloads: dict[str, dict[str, object]] = {}

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
                if self.container.timeline_client is not None:
                    await self.container.timeline_client.disconnect()
                await self.container.home_assistant.disconnect()
                self.container.memory_store.close()
                self.container.knowledge_store.close()
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
        max_messages = conversation_config.get("max_messages", 12)
        if not isinstance(max_messages, int) or isinstance(max_messages, bool) or max_messages < 2:
            raise ValueError("conversation.max_messages must be an integer of at least 2")

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
        self.container.conversation = Conversation(max_messages)
        self.container.memory_store = SQLiteMemoryStore(database_file)
        self.container.knowledge_store = SQLiteKnowledgeStore(database_file)
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
        clock = lambda: datetime.now(timezone.utc)
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
        action_config = self.general.get("home_assistant", {}).get("action_policy", {})
        self.container.home_assistant_capability_context = HomeAssistantCapabilityContext(
            catalog,
            self.general["home_assistant"].get("allowed_read_entities", ()),
            action_config.get("allowed_entities", ()),
            tuple(action_config.get("confirm_required", ())) + tuple(action_config.get("high_impact", ())),
            self.general["home_assistant"].get("entity_aliases", {}),
        )
        self.container.home_access_enrollment = HomeAccessEnrollment(
            self.container.config_loader.config_folder / "general.yaml", catalog
        )
        self.container.home_assistant_action_gateway = ConfirmedHomeAssistantActionGateway(
            HomeAssistantCapabilityGateway(catalog),
            HomeAssistantRiskPolicy(
                action_config.get("confirm_required", ()),
                action_config.get("high_impact", ()),
                action_config.get("allowed_entities", ()),
            ),
            PendingActionStore(),
            self.container.home_assistant,
        )
        self.container.read_only_assistant.set_action_gateway(
            self.container.home_assistant_action_gateway
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

        self.container.logger.info(
            f"Loaded {self.container.entity_registry.count()} entities into registry."
        )

    async def startup_checks(self):
        """
        Run startup verification checks.
        """

        self.container.logger.info(
            f"Home Assistant ready with {self.container.entity_registry.count()} discovered entities, "
            f"{len(self.general['home_assistant']['allowed_read_entities'])} allowed reads, and "
            f"{len(self.general['home_assistant']['action_policy']['allowed_entities'])} allowed action entities."
        )

        self.container.logger.info("Provider startup checks are connectivity-only.")

    async def handle_request(self, text: str) -> dict[str, object]:
        """Route one user request through the configured safe assistant slice."""

        if not hasattr(self.container, "read_only_assistant"):
            return {"status": "not_supported", "message": "Assistant runtime is unavailable."}
        conversation = self.container.conversation
        conversation.add_user_message(text)
        request_context = RequestContext(Request(text))
        package = self.container.runtime_context_assembler.assemble(request_context)
        context = {
            "memory": self._context_items(package.memory),
            "knowledge": self._context_items(package.knowledge),
            "conversation": tuple(message.to_openai() for message in conversation.history()[:-1]),
            "home_assistant": self.container.home_assistant_capability_context.as_context(),
        }
        result = await self.container.read_only_assistant.handle(text, context)
        message = self._user_message(result)
        if message:
            conversation.add_assistant_message(message)
        return result

    @staticmethod
    def _user_message(result: dict[str, object]) -> str:
        """Return a stable, safe console response for every runtime outcome."""
        messages = {
            "success": "Action completed." if "message" not in result else str(result["message"]),
            "clarification_required": "Please specify the exact configured entity you mean.",
            "not_supported": "That request is not available in the current configuration.",
            "unavailable": "Home Assistant is temporarily unavailable. Please try again.",
            "forbidden": "That action is not authorized.",
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
                payload = self._pending_action_payloads.pop(token, None)
                try:
                    result = ({"status": "forbidden", "message": "Confirmation is invalid."}
                              if payload is None else await self.container.read_only_assistant.confirm_action(token, payload))
                except Exception:
                    result = {"status": "unavailable"}
                message = self._user_message(result)
                self.container.conversation.add_assistant_message(message)
                self.console.print(f"Jarvis [{result['status']}]: {message}")
                continue
            result = await self.handle_request(text)
            if result.get("status") == "requires_confirmation":
                token = result.get("token")
                payload = result.pop("action_payload", None)
                if token and payload:
                    self._pending_action_payloads[token] = payload
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
        return {"status":"not_supported","message":"Use: home discover [domain], home enroll read <entity>, home enroll action <entity> <service> [normal|high], or home alias <name> <entity>."}

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
            "confirm_required": policy.get("confirm_required", ()),
            "high_impact": policy.get("high_impact", ()),
            "allowed_entities": policy.get("allowed_entities", ()),
        }.items():
            if not isinstance(values, (list, tuple)) or any(
                not isinstance(value, str) or not value.strip() for value in values
            ):
                raise ValueError(f"home_assistant.{name} must be a list of non-empty strings.")
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
