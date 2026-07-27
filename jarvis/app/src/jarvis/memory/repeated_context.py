"""Conservative extraction and promotion of repeated user-authored context."""

from __future__ import annotations

import json
import re
from secrets import token_urlsafe

from jarvis.models.conversation_memory import RepeatedContextCandidate
from jarvis.models.memory import MemoryConsentLevel, MemorySource, MemoryType
from jarvis.models.memory_write import ExplicitMemoryWriteRequest, MemoryWriteStatus


_EXTRACTION_INSTRUCTIONS = """Extract at most one stable, user-authored memory candidate.
Return JSON only: {"candidate":null} or
{"candidate":{"key":"canonical subject/property key","content":"concise standalone fact",
"category":"fact|preference|routine|relationship|name|home_terminology",
"sensitive":false}}.
Accept only a stable fact, preference, routine, relationship, name, or home term asserted
by the user. Reject questions, commands, device states, action results, temporary plans,
transient conditions, assistant claims, and inferences. Mark health, finance, identity,
precise location, credentials, security, and similarly private data sensitive."""


class RepeatedContextExtractor:
    def __init__(self, provider) -> None:
        self._provider = provider

    def extract(self, text: str) -> RepeatedContextCandidate | None:
        normalized = " ".join(text.split())
        if not self._eligible_shape(normalized):
            return None
        response = self._provider.ask({
            "instructions": _EXTRACTION_INSTRUCTIONS,
            "input": [{"role": "user", "content": normalized}],
        })
        try:
            value = json.loads(response)
            candidate = value.get("candidate")
            if candidate is None:
                return None
            key = candidate["key"].strip()
            content = candidate["content"].strip()
            category = candidate["category"].strip()
            sensitive = candidate["sensitive"]
        except (TypeError, ValueError, KeyError, AttributeError):
            return None
        if (
            not key or not content or len(key) > 240 or len(content) > 1000
            or category not in {"fact", "preference", "routine", "relationship", "name", "home_terminology"}
            or not isinstance(sensitive, bool)
        ):
            return None
        return RepeatedContextCandidate(key, content, category, sensitive)

    @staticmethod
    def _eligible_shape(text: str) -> bool:
        lower = text.casefold().strip(" .")
        if len(lower) < 8 or "?" in text:
            return False
        if lower.startswith((
            "turn ", "switch ", "set ", "open ", "close ", "lock ", "unlock ",
            "start ", "stop ", "press ", "what ", "who ", "where ", "when ",
            "why ", "how ", "is ", "are ", "do ", "does ", "did ", "can ",
            "could ", "would ", "please ", "confirm ", "memory ", "knowledge ",
            "forget ", "remember ", "clear ",
        )):
            return False
        if re.search(r"\b(is|are) (on|off|open|closed|unavailable|unknown)\b", lower):
            return False
        return True


class RepeatedContextLearner:
    """Promote only the third distinct occurrence of a validated candidate."""

    def __init__(self, conversation_store, memory_store, memory_writer, extractor) -> None:
        self._conversations = conversation_store
        self._memories = memory_store
        self._writer = memory_writer
        self._extractor = extractor
        self._pending_sensitive: dict[str, RepeatedContextCandidate] = {}

    def observe(self, message) -> dict[str, object] | None:
        candidate = self._extractor.extract(message.content)
        if candidate is None or self._conversations.is_promoted(candidate.key):
            return None
        count = self._conversations.record_candidate(
            message.message_id,
            candidate.key,
            candidate.content,
            candidate.category,
            candidate.is_sensitive,
        )
        if count < 3:
            return None
        if self._duplicate(candidate.content):
            self._conversations.mark_promoted(candidate.key, None)
            return None
        if candidate.is_sensitive:
            token = token_urlsafe(18)
            self._pending_sensitive[token] = candidate
            return {
                "status": "requires_confirmation",
                "message": (
                    "You have mentioned this private detail three times. "
                    f"Shall I remember it permanently? Reply: confirm memory {token}"
                ),
                "confirmation_token": token,
            }
        result = self._write(candidate, confirmed=False)
        if result.record is not None:
            self._conversations.mark_promoted(candidate.key, result.record.memory_id)
        return None

    def confirm(self, token: str) -> dict[str, object]:
        candidate = self._pending_sensitive.pop(token, None)
        if candidate is None:
            return {"status": "forbidden", "message": "That memory confirmation is invalid or has expired."}
        result = self._write(candidate, confirmed=True)
        if result.record is None:
            return {"status": "unavailable", "message": "I could not save that memory."}
        self._conversations.mark_promoted(candidate.key, result.record.memory_id)
        return {"status": "success", "message": "Understood. I will remember that private detail."}

    def _write(self, candidate: RepeatedContextCandidate, confirmed: bool):
        return self._writer.create_explicit_memory(ExplicitMemoryWriteRequest(
            content=candidate.content,
            memory_type=MemoryType.PREFERENCE if candidate.category == "preference" else MemoryType.FACT,
            source=MemorySource.REPEATED_USER_CONTEXT,
            consent_level=MemoryConsentLevel.EXPLICIT,
            is_explicit=False,
            is_sensitive=candidate.is_sensitive,
            has_sensitive_confirmation=confirmed,
            confidence=1.0,
            tags=("automatically_learned", candidate.category),
            metadata={"provenance": "repeated_user_context", "occurrence_threshold": 3},
        ))

    def _duplicate(self, content: str) -> bool:
        normalized = " ".join(content.casefold().split())
        return any(
            record.status.value == "active"
            and " ".join(record.content.casefold().split()) == normalized
            for record in self._memories.list_records()
        )
