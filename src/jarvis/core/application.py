"""
Project Jarvis

Main application class.
"""

from rich.console import Console
from rich.panel import Panel

from jarvis.core.container import ServiceContainer
from jarvis.homeassistant.client import HomeAssistantClient

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


    def run(self):
        """
        Start Jarvis.
        """
        self.load_configuration()
        self.initialize_services()
        self.connect_services()

        self.status = "Running"
        
        self.show_banner()
        self.console.print("[green]✓ Jarvis started successfully[/green]")
        if self.debug_mode:
            self.console.print("[magenta]Debug mode is enabled[/magenta]")
            current_status = self.get_status()
            status_message = f"Current status: {current_status}"
            startup_steps = [
                "Configuration loaded",
                "Banner displayed",
                "Application running"
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

        if current_status == "Running":
            self.say_goodbye("Goodbye from Project Jarvis!")
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
        )
    def connect_services(self):
        """
        Connect external services.
        """

        self.container.home_assistant.connect()
        
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
            border_style="cyan"
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