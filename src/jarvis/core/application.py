"""
Project Jarvis

Main application class.
"""

import asyncio
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
        await self.connect_services()
        await self.startup_checks()

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
            await self.keep_running()
        else:
            self.console.print("[red]Jarvis is not running.[/red]")

    def load_configuration(self):
        """
        Load the application configuration.
        """
        self.general = self.container.config_loader.load()

        self.container.logger.info("Configuration loaded")

        self.container.event_bus.publish("ApplicationStarted")

    def initialize_services(self):
        """
        Create shared services.
        """

        ha_config = self.general["home_assistant"]
        self._validate_home_assistant_policy(ha_config)

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
        self.container.memory_store = InMemoryMemoryStore()
        self.container.knowledge_store = InMemoryKnowledgeStore()
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
        self.container.read_only_assistant = create_read_only_assistant(
            self.container.openai,
            self.container.home_assistant,
            allowed_read_entities,
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

        self.container.logger.info(
            f"Loaded {self.container.entity_registry.count()} entities into registry."
        )

    async def startup_checks(self):
        """
        Run startup verification checks.
        """

        self.container.logger.info("Available lights:")

        for entity in self.container.entity_registry.all():
            if entity.entity_id.startswith("light."):
                self.console.print(entity.entity_id)

        self.container.logger.info(
            "Home Assistant startup checks are read-only."
        )

        self.container.logger.info("Provider startup checks are connectivity-only.")

    async def handle_request(self, text: str) -> dict[str, object]:
        """Route one user request through the configured safe assistant slice."""

        if not hasattr(self.container, "read_only_assistant"):
            return {"status": "not_supported", "message": "Assistant runtime is unavailable."}
        request_context = RequestContext(Request(text))
        package = self.container.runtime_context_assembler.assemble(request_context)
        context = {
            "memory": self._context_items(package.memory),
            "knowledge": self._context_items(package.knowledge),
        }
        return await self.container.read_only_assistant.handle(text, context)

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
            if text.strip().startswith("confirm "):
                token = text.strip().split(maxsplit=1)[1]
                payload = self._pending_action_payloads.pop(token, None)
                result = ({"status": "forbidden", "message": "Confirmation is invalid."}
                          if payload is None else await self.container.read_only_assistant.confirm_action(token, payload))
                self.console.print(f"Jarvis [{result['status']}]: {result.get('message', result.get('reason_code', 'Action completed.'))}")
                continue
            result = await self.handle_request(text)
            if result.get("status") == "requires_confirmation":
                token = result.get("token")
                payload = result.pop("action_payload", None)
                if token and payload:
                    self._pending_action_payloads[token] = payload
                    self.console.print(f"Confirm action: {result.get('summary', '')}. Type: confirm {token}")
                    continue
            self.console.print(f"Jarvis [{result['status']}]: {result['message']}")

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
