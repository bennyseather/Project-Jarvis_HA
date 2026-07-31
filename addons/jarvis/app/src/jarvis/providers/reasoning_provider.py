"""Provider-neutral reasoning contract for OpenAI now and Ollama later."""

from typing import Protocol


class ReasoningProvider(Protocol):
    def reason(
        self,
        *,
        instructions: str,
        input_messages: list[dict[str, str]],
        model: str,
        timeout_seconds: int,
    ) -> dict[str, object]:
        """Return a typed response with message, usage, and estimated cost."""
