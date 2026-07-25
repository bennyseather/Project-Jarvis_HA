"""
Project Jarvis

Main application class.
"""

import asyncio

from rich.console import Console
from rich.panel import Panel

from jarvis.core.assistant import Assistant
from jarvis.core.container import ServiceContainer
from jarvis.core.context_builder import ContextBuilder
from jarvis.homeassistant.client import HomeAssistantClient
from jarvis.homeassistant.entity_resolver import EntityResolver
from jarvis.providers.openai_provider import OpenAIProvider
from jarvis.core.assistant_factory import create_read_only_assistant


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

        self.container.assistant = Assistant(
            openai=self.container.openai,
            context_builder=self.container.context_builder,
        )

        self.container.entity_resolver = EntityResolver(
            self.container.entity_registry
        )


    async def connect_services(self):
        """
        Connect external services.
        """

        entities = await self.container.home_assistant.connect()

        self.container.entity_registry.load(entities)

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

        allowed_read_entities = frozenset(
            self.general.get("home_assistant", {}).get("allowed_read_entities", ())
        )
        self.container.read_only_assistant = create_read_only_assistant(
            self.container.openai,
            self.container.home_assistant,
            allowed_read_entities,
        )

        self.container.logger.info("Provider startup checks are connectivity-only.")

    async def handle_request(self, text: str) -> dict[str, object]:
        """Route one user request through the configured safe assistant slice."""

        if not hasattr(self.container, "read_only_assistant"):
            return {"status": "not_supported", "message": "Assistant runtime is unavailable."}
        return await self.container.read_only_assistant.handle(text)

    async def keep_running(self):
        """Run the first minimal interactive request loop."""

        self.console.print("[green]Jarvis is ready. Type 'quit' to exit.[/green]")
        while True:
            text = await asyncio.to_thread(input, "You: ")
            if text.strip().casefold() in {"quit", "exit"}:
                return
            if not text.strip():
                continue
            result = await self.handle_request(text)
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
