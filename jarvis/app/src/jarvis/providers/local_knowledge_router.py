"""Deterministic local-first routing for stable general knowledge."""

from __future__ import annotations


class LocalKnowledgeRouter:
    """Use one Ollama answer pass before considering live research."""

    _EXPLICIT_RESEARCH = (
        "search", "research", "look up", "web search", "browse", "verify online",
    )
    _FRESHNESS = (
        "latest", "current", "today", "tonight", "yesterday", "tomorrow",
        "news", "headline", "release", "version", "price", "cost right now",
        "schedule", "score", "standings", "election", "president", "prime minister",
        "chief executive", "ceo", "law", "regulation", "exchange rate", "stock",
    )
    _HOME_TERMS = {
        "alarm", "blind", "blinds", "camera", "climate", "cover", "curtain",
        "device", "door", "fan", "garage", "heater", "heating", "home", "house",
        "humidity", "light", "lights", "lock", "mower", "room", "scene", "sensor",
        "speaker", "switch", "temperature", "thermostat", "vacuum", "washing", "window",
    }
    _UNCERTAIN = (
        "i don't know", "i do not know", "i'm not sure", "i am not sure",
        "cannot verify", "can't verify", "insufficient information",
        "not enough information", "uncertain",
    )

    def __init__(self, reasoning) -> None:
        self._reasoning = reasoning

    def requires_live_research(self, text: str) -> bool:
        """Return whether the wording requires fresh public information."""
        normalized = " ".join(text.casefold().strip(" .?!").split())
        return bool(normalized) and (
            any(marker in normalized for marker in self._EXPLICIT_RESEARCH)
            or any(marker in normalized for marker in self._FRESHNESS)
        )

    def handle(self, text, context, *, voice_mode=False):
        normalized = " ".join(text.casefold().strip(" .?!").split())
        words = set(normalized.split())
        if (
            not normalized
            or self.requires_live_research(text)
            or words & self._HOME_TERMS
        ):
            return None
        history = tuple(context.get("conversation", ()))
        messages = [
            {"role": item["role"], "content": item["content"]}
            for item in history[-4:]
            if isinstance(item, dict)
            and item.get("role") in {"user", "assistant"}
            and isinstance(item.get("content"), str)
        ]
        messages.append({"role": "user", "content": text})
        request = {
            "instructions": (
                "Answer from stable general knowledge in concise British English. "
                + ("Use at most two short spoken sentences. " if voice_mode else "")
                + "State uncertainty plainly. Do not claim current facts, browse the web, "
                "or perform Home Assistant actions."
            ),
            "input_messages": messages,
            "timeout_seconds": 45,
        }
        if voice_mode and hasattr(self._reasoning, "policy"):
            request["model"] = self._reasoning.policy.voice_model
        local_reason = getattr(self._reasoning, "reason_local", None)
        result = (
            local_reason(**request)
            if local_reason is not None
            else self._reasoning.reason(model="local", **request)
        )
        if result.get("status") != "success":
            return None
        message = str(result.get("message", "")).strip()
        if not message or any(marker in message.casefold() for marker in self._UNCERTAIN):
            return None
        return {
            "status": "success",
            "message": message,
            "provider": "ollama",
            "researched": False,
        }
