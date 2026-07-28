"""Natural user controls for proactive assistance."""

from __future__ import annotations


class NaturalProactiveController:
    def __init__(self, manager) -> None:
        self._manager = manager

    async def handle(self, text: str, conversation_id: str):
        normalized = " ".join(text.casefold().split()).strip(" .?!")
        if normalized in {
            "what needs my attention",
            "show pending suggestions",
            "what should i know",
            "anything i should know",
        }:
            return self._manager.attention(conversation_id)
        if normalized in {
            "why are you suggesting that",
            "why did you suggest that",
            "explain that suggestion",
        }:
            return self._manager.explain_current(conversation_id)
        if normalized in {"do it", "apply that suggestion"}:
            return await self._manager.accept_current(conversation_id)
        if normalized in {"not now", "later", "remind me later"}:
            return self._manager.snooze_current(conversation_id)
        if normalized in {
            "never suggest this again",
            "do not suggest this again",
            "stop suggesting that",
        }:
            return self._manager.suppress_current(conversation_id)
        if normalized in {"clear pending suggestions", "clear all suggestions"}:
            return self._manager.clear_pending()
        if normalized in {"show suppressed suggestions", "show suggestion suppressions"}:
            return self._manager.show_suppressions()
        if normalized in {"clear suggestion suppressions", "allow all suggestions again"}:
            return self._manager.clear_suppressions()
        return None
