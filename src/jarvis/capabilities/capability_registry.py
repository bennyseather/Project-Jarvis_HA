"""
Registry of executable capabilities.
"""

from __future__ import annotations

from typing import Any


class CapabilityRegistry:
    """
    Stores all registered capabilities.

    Capabilities are registered once during startup and
    looked up by name during execution.
    """

    def __init__(self) -> None:
        self._capabilities: dict[str, Any] = {}

    def register(
        self,
        name: str,
        capability: Any,
    ) -> None:
        """
        Register a capability.
        """

        self._capabilities[name] = capability

    def get(self, name: str) -> Any | None:
        """
        Retrieve a capability by name.
        """

        return self._capabilities.get(name)

    def exists(self, name: str) -> bool:
        """
        Check whether a capability exists.
        """

        return name in self._capabilities

    def all(self) -> dict[str, Any]:
        """
        Return all registered capabilities.
        """

        return self._capabilities