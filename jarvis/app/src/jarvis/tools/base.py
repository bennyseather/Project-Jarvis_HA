"""
Base Tool interface for Project Jarvis.
"""

from abc import ABC, abstractmethod


class Tool(ABC):
    """
    Base class for every Jarvis tool.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Unique tool name.
        """
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """
        Human-readable description of the tool.
        """
        ...

    @property
    @abstractmethod
    def schema(self) -> dict:
        """
        JSON schema describing the tool arguments.

        This will later be sent to the reasoning engine.
        """
        ...

    @abstractmethod
    def execute(self, **kwargs):
        """
        Execute the tool.
        """
        ...