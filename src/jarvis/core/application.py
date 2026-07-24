"""
Project Jarvis

Main application class.
"""

import asyncio

from rich.console import Console
from rich.panel import Panel

from jarvis.capabilities.turn_on_light import TurnOnLightCapability
from jarvis.core.assistant import Assistant
from jarvis.core.container import ServiceContainer
from jarvis.core.context_builder import ContextBuilder
from jarvis.homeassistant.client import HomeAssistantClient
from jarvis.homeassistant.entity_resolver import EntityResolver
from jarvis.providers.openai_provider import OpenAIProvider


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

        self.container.turn_on_light = TurnOnLightCapability(
            home_assistant=self.container.home_assistant,
            resolver=self.container.entity_resolver,
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

        self.container.logger.info("Testing TurnOnLightCapability...")

        success = await self.container.turn_on_light.execute("blocks")

        if success:
            self.container.logger.info(
                "TurnOnLightCapability completed successfully."
            )
        else:
            self.container.logger.error(
                "TurnOnLightCapability failed."
            )

        self.container.logger.info("Connecting to OpenAI...")

        self.container.logger.info("Testing conversation...")

        response = self.container.assistant.ask(
            "My favourite colour is blue."
        )
        self.container.logger.info(f"Jarvis: {response}")

        response = self.container.assistant.ask(
            "What is my favourite colour?"
        )
        self.container.logger.info(f"Jarvis: {response}")

    async def keep_running(self):
        """
        Keep Jarvis alive and ready for work.
        """

        self.console.print(
            "[green]Jarvis is ready and waiting for work...[/green]"
        )

        try:
            while True:
                await asyncio.sleep(1)

        except asyncio.CancelledError:
            raise

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