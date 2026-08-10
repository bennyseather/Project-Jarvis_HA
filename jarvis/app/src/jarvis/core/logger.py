"""
Logging for Project Jarvis.
"""

from rich.console import Console


class JarvisLogger:
    """
    Handles application logging.
    """

    def __init__(self):
        self.console = Console()

    def info(self, message: str):
        self.console.print(f"[green][INFO][/green] {message}")

    def warning(self, message: str):
        self.console.print(f"[yellow][WARNING][/yellow] {message}")

    def error(self, message: str):
        self.console.print(f"[red][ERROR][/red] {message}")

    def debug(self, message: str):
        self.console.print(f"[cyan][DEBUG][/cyan] {message}")