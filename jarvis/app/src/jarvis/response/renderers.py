"""Provider-neutral response renderer contracts."""

from __future__ import annotations

from typing import Protocol

from jarvis.models.response import Response


class ResponseRenderer(Protocol):
    """Transforms a normalized response for a presentation layer."""

    def render(self, response: Response) -> Response:
        """Return a presentation-layer representation of ``response``."""


class StructuredResponseRenderer:
    """Return the normalized Response without additional formatting."""

    def render(self, response: Response) -> Response:
        """Return ``response`` unchanged."""

        return response
