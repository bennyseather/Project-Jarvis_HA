"""
Tool registry for Project Jarvis.
"""

from jarvis.tools.base import Tool


class ToolRegistry:
    """
    Stores every tool available to Jarvis.
    """

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool):
        """
        Register a tool.
        """
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        """
        Get a tool by name.
        """
        return self._tools.get(name)

    def all(self) -> list[Tool]:
        """
        Return every registered tool.
        """
        return list(self._tools.values())

    def count(self) -> int:
        """
        Number of registered tools.
        """
        return len(self._tools)