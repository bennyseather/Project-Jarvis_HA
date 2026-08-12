"""Deterministic, safety-subordinate response presentation."""

from __future__ import annotations

import re


class PersonalityPresenter:
    """Shape presentation without changing facts, actions, or policy outcomes."""

    _SERIOUS_STATUSES = {
        "requires_confirmation", "clarification_required", "forbidden",
        "failed", "failure", "unavailable", "error", "not_supported",
    }
    _MANAGEMENT_PHRASES = {
        "show personality", "explain personality", "show relationship preferences",
        "explain last response style", "reset personality",
        "show personality diagnostics", "personality diagnostics",
        "forget personality preferences", "forget relationship preferences",
    }

    def __init__(self, manager):
        self._manager = manager

    def present(self, result, request, conversation_id, *, voice_mode=False):
        if not isinstance(result, dict) or not isinstance(result.get("message"), str):
            return result
        message = result["message"].strip()
        if not message:
            return result
        normalized = " ".join(request.casefold().strip(" .?!").split())
        status = str(result.get("status", "unavailable"))
        serious = status in self._SERIOUS_STATUSES
        management = (
            normalized in self._MANAGEMENT_PHRASES
            or normalized.startswith("set personality ")
            or normalized.startswith("address me as ")
        )
        if management:
            return result
        profile = self._manager.profile()
        changes = []
        mode = self._mode(result, normalized, serious)
        influences = ["voice" if voice_mode else "text", mode]
        if profile.address:
            influences.append("explicit preferred address available")

        if voice_mode and not serious and not management:
            researched = bool(result.get("researched") or result.get("sources"))
            shaped = self._for_voice(
                message,
                profile.verbosity,
                omit_links=researched,
                preserve_list=bool(result.get("preserve_voice_list")),
            )
            if shaped != message:
                message = shaped
                changes.append(
                    "shortened for voice without spoken source links"
                    if researched else "shortened for voice"
                )

        if (
            not serious
            and not management
            and profile.address
            and self._is_greeting(normalized)
            and profile.address.casefold() not in message.casefold()
        ):
            message = f"Hello, {profile.address}. {message}"
            changes.append("used the explicit preferred address")

        explanation = (
            "The last response preserved the underlying facts and action result. "
            + (
                "Its presentation was " + ", ".join(changes) + "."
                if changes
                else (
                    f"It used the {profile.formality}, {profile.warmth}, "
                    f"{profile.verbosity} profile without additional transformation."
                )
            )
            + (" Humour was suppressed because the context was serious." if serious else "")
        )
        self._manager.record_style(conversation_id, explanation)
        self._manager.record_diagnostic(conversation_id, {
            "mode": mode,
            "profile": (
                f"{profile.formality}/{profile.warmth}/{profile.verbosity}/"
                f"humour-{profile.humour}/{profile.proactivity}"
            ),
            "influences": tuple(influences + changes),
        })
        if message == result["message"]:
            return result
        presented = dict(result)
        presented["message"] = message
        return presented

    @staticmethod
    def _is_greeting(normalized):
        return normalized in {
            "hello", "hi", "hey", "good morning", "good afternoon",
            "good evening", "hello jarvis", "hi jarvis",
        }

    @staticmethod
    def _mode(result, normalized, serious):
        if serious:
            return "protected exact response"
        if result.get("researched") or result.get("sources"):
            return "research summary"
        if any(word in normalized for word in ("light", "switch", "temperature", "home", "house", "room")):
            return "home interaction"
        if normalized.startswith(("why ", "how ", "what ", "who ", "where ", "when ")):
            return "informational dialogue"
        return "general dialogue"

    @staticmethod
    def _for_voice(message, verbosity, *, omit_links=False, preserve_list=False):
        text = re.sub(r"\n+Sources:\n.*", "", message, flags=re.DOTALL | re.IGNORECASE)
        if omit_links:
            text = re.sub(r"\[([^\]]+)\]\(https?://[^)]+\)", r"\1", text)
            text = re.sub(r"https?://\S+", "", text)
        text = re.sub(r"[*_`#]", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        text = re.sub(
            r"^(?:certainly|of course|understood|very good)[,!.]?\s+",
            "",
            text,
            flags=re.IGNORECASE,
        )
        sentence_limit = 10 if preserve_list else (1 if verbosity == "concise" else 2)
        sentences = re.split(r"(?<=[.!?])\s+", text)
        text = " ".join(sentences[:sentence_limit])
        character_limit = 900 if preserve_list else (220 if verbosity == "concise" else 360)
        if len(text) > character_limit:
            shortened = text[:character_limit].rsplit(" ", 1)[0].rstrip(" ,;:")
            text = shortened + "."
        return text
