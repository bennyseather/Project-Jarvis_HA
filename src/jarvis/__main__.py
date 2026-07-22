"""
Project Jarvis
Main application entry point.
"""

from rich.console import Console

from jarvis.config.loader import ConfigLoader

console = Console()


def main():

    config = ConfigLoader()

    general = config.load("general.yaml")

    console.print()
    console.print("[bold cyan]=========================================[/bold cyan]")
    console.print(
        f"[bold cyan]        {general['project']['name']}[/bold cyan]"
    )
    console.print("[bold cyan]=========================================[/bold cyan]")
    console.print()

    console.print(
        f"[green]Version : {general['project']['version']}[/green]"
    )

    console.print("[yellow]Status  : Starting...[/yellow]")
    console.print()

    console.print("[green]✓ Configuration loaded[/green]")
    console.print("[green]✓ Jarvis started successfully[/green]")


if __name__ == "__main__":
    main()