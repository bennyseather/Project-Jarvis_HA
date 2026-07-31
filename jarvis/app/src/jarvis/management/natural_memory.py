"""Friendly natural-language access to Jarvis memory controls."""

from __future__ import annotations

import re
from secrets import token_urlsafe

from jarvis.models.memory import MemoryConsentLevel, MemorySource, MemoryType
from jarvis.models.memory_write import ExplicitMemoryWriteRequest, MemoryCorrectionRequest


class NaturalMemoryController:
    def __init__(
        self,
        memory_store,
        memory_writer,
        conversation_store,
        learner,
        reflection_manager=None,
        episodic_manager=None,
    ) -> None:
        self._memories = memory_store
        self._writer = memory_writer
        self._conversations = conversation_store
        self._learner = learner
        self._reflections = reflection_manager
        self._episodic = episodic_manager
        self._pending_sensitive: dict[str, str] = {}

    def handle(self, text: str, conversation_id: str | None) -> dict[str, object] | None:
        raw = text.strip()
        lower = " ".join(raw.casefold().split()).strip(" .?!")
        if self._episodic is not None:
            episodic_result = self._episodic.handle(raw, conversation_id)
            if episodic_result is not None:
                return episodic_result
        token = self._match(r"confirm memory (.+)", raw)
        if token:
            content = self._pending_sensitive.pop(token, None)
            if content is not None:
                result = self._writer.create_explicit_memory(ExplicitMemoryWriteRequest(
                    content,
                    MemoryType.FACT,
                    MemorySource.EXPLICIT_USER_REQUEST,
                    MemoryConsentLevel.EXPLICIT,
                    is_sensitive=True,
                    has_sensitive_confirmation=True,
                ))
                self._refresh_reflections()
                return {
                    "status": "success" if result.record else result.status.value,
                    "message": "Understood. I will remember that private detail." if result.record else "I could not save that memory.",
                }
            if self._episodic is not None:
                episodic_result = self._episodic.confirm(token)
                if episodic_result is not None:
                    return episodic_result
            return self._learner.confirm(token)
        if lower in {
            "do not learn from this conversation",
            "don't learn from this conversation",
            "stop learning from this conversation",
        }:
            self._conversations.set_learning_disabled(conversation_id, True)
            return {
                "status": "success",
                "message": "Understood. I will not promote repeated context from this conversation.",
            }
        if lower in {
            "learn from this conversation again",
            "resume learning from this conversation",
        }:
            self._conversations.set_learning_disabled(conversation_id, False)
            return {
                "status": "success",
                "message": "Understood. Repeated-context learning is enabled for this conversation.",
            }
        if self._looks_like_style_feedback(lower):
            result = self._writer.create_explicit_memory(ExplicitMemoryWriteRequest(
                f"The user requests this interaction style: {raw}",
                MemoryType.PREFERENCE,
                MemorySource.EXPLICIT_USER_REQUEST,
                MemoryConsentLevel.EXPLICIT,
                tags=("style_preference",),
                confidence=1.0,
                metadata={
                    "provenance": "explicit_style_feedback",
                    "source_conversation_ids": [
                        self._conversations.normalize_conversation_id(conversation_id)
                    ],
                },
            ))
            self._refresh_reflections()
            return {
                "status": "success" if result.record else result.status.value,
                "message": "Understood. I will apply that response preference."
                if result.record else "I could not save that response preference.",
            }
        remembered = self._match(r"(?:please )?remember(?: that)? (.+)", raw)
        if remembered:
            if self._looks_sensitive(remembered):
                token = token_urlsafe(18)
                self._pending_sensitive[token] = remembered
                return {
                    "status": "requires_confirmation",
                    "message": (
                        "That appears to be private information. I will only store it after "
                        f"explicit confirmation. Reply: confirm memory {token}"
                    ),
                    "confirmation_token": token,
                }
            result = self._writer.create_explicit_memory(ExplicitMemoryWriteRequest(
                remembered,
                MemoryType.FACT,
                MemorySource.EXPLICIT_USER_REQUEST,
                MemoryConsentLevel.EXPLICIT,
            ))
            self._refresh_reflections()
            return {
                "status": "success" if result.record else result.status.value,
                "message": "Certainly. I will remember that." if result.record else "I could not save that memory.",
            }
        if lower in {
            "what do you remember", "what do you remember about me",
            "list my memories", "show my memories",
        }:
            records = self._visible_records()
            if not records:
                return {"status": "success", "message": "I do not yet have any durable memories about you."}
            return {"status": "success", "message": "I remember: " + "; ".join(record.content for record in records[:10])}
        if lower in {
            "what have you learned about me",
            "what have you learned",
            "summarize what you have learned about me",
        }:
            records = self._visible_records()
            if not records:
                return {"status": "success", "message": "I have not learned any durable information about you yet."}
            reflection_count = 0 if self._reflections is None else len(
                tuple(record for record in self._reflections.records() if not record.sensitive)
            )
            return {
                "status": "success",
                "message": (
                    "I have learned: " + "; ".join(record.content for record in records[:10])
                    + f". I currently hold {reflection_count} inspectable connection"
                    f"{'s' if reflection_count != 1 else ''} between approved memories."
                ),
            }
        if lower in {
            "what are you uncertain about",
            "what are you unsure about",
            "what contradictions do you remember",
        }:
            uncertain = () if self._reflections is None else self._reflections.uncertainties()
            if not uncertain:
                return {"status": "success", "message": "I have no recorded contradictions or low-confidence memories."}
            return {
                "status": "success",
                "message": "I am uncertain about: " + "; ".join(
                    record.content for record in uncertain[:5]
                ),
            }
        if lower in {
            "show memory connections",
            "what memories are connected",
            "show what you have connected",
        }:
            records = () if self._reflections is None else tuple(
                record for record in self._reflections.records()
                if not record.sensitive
            )
            if not records:
                return {"status": "success", "message": "I have no inspectable memory connections yet."}
            return {
                "status": "success",
                "message": "Inspectable connections: " + "; ".join(
                    f"{record.kind.value}: {record.content}" for record in records[:5]
                ),
            }
        if lower in {
            "what have you learned automatically", "what did you learn automatically",
            "show automatically learned memories",
        }:
            records = [record for record in self._visible_records() if record.source is MemorySource.REPEATED_USER_CONTEXT]
            if not records:
                return {"status": "success", "message": "I have not promoted any repeated context yet."}
            return {"status": "success", "message": "From repeated context, I learned: " + "; ".join(record.content for record in records[:10])}
        subject = self._match(r"(?:what|why) do you remember about (.+)", raw)
        if subject:
            matches = self._find(subject)
            if not matches:
                return {"status": "success", "message": "I do not have a durable memory matching that."}
            record = matches[0]
            provenance = (
                "you explicitly asked me to remember it"
                if record.source is MemorySource.EXPLICIT_USER_REQUEST
                else "you stated equivalent context in at least three separate messages"
            )
            return {"status": "success", "message": f"I remember that {record.content}. The source is: {provenance}."}
        if lower in {"why do you remember that", "why do you remember this"}:
            records = self._visible_records()
            if len(records) != 1:
                return {
                    "status": "clarification_required",
                    "message": "Please name the remembered information you want provenance for.",
                }
            record = records[0]
            provenance = (
                "you explicitly asked me to remember it"
                if record.source is MemorySource.EXPLICIT_USER_REQUEST
                else "you stated equivalent context in at least three separate messages"
            )
            return {
                "status": "success",
                "message": f"I remember that {record.content}. The source is: {provenance}.",
            }
        connected = self._match(r"(?:please )?forget everything connected to (.+)", raw)
        if connected:
            matches = self._find(connected)
            if not matches:
                return {"status": "success", "message": "I found no connected durable memory."}
            identifiers = {record.memory_id for record in matches}
            if self._reflections is not None:
                identifiers = set(self._reflections.connected_memory_ids(identifiers))
            visible = {record.memory_id for record in self._visible_records()}
            deleted = 0
            for memory_id in sorted(identifiers & visible):
                self._memories.delete(memory_id)
                deleted += 1
            self._refresh_reflections()
            return {
                "status": "success",
                "message": f"Done. I permanently deleted {deleted} connected memor"
                f"{'ies' if deleted != 1 else 'y'}.",
            }
        forgotten = self._match(r"(?:please )?forget(?: that)? (.+)", raw)
        if forgotten:
            matches = self._find(forgotten)
            if not matches:
                return {"status": "success", "message": "I found no matching durable memory."}
            if len(matches) > 1:
                return {"status": "clarification_required", "message": "More than one memory matches. Please be more specific."}
            self._memories.delete(matches[0].memory_id)
            self._refresh_reflections()
            return {"status": "success", "message": "Done. That memory has been permanently deleted."}
        correction = re.fullmatch(r"(?:please )?correct (.+?) to (.+)", raw, re.IGNORECASE)
        if correction:
            matches = self._find(correction.group(1))
            if len(matches) != 1:
                return {"status": "clarification_required", "message": "Please identify one existing memory to correct."}
            result = self._writer.correct_memory(MemoryCorrectionRequest(
                matches[0].memory_id,
                correction.group(2).strip(),
                MemorySource.USER_CORRECTION,
                MemoryConsentLevel.EXPLICIT,
            ))
            self._refresh_reflections()
            return {"status": "success" if result.record else result.status.value, "message": "Understood. I have replaced the old memory."}
        if lower in {
            "clear my recent conversations", "clear recent conversations",
            "forget my recent conversations",
        }:
            count = self._conversations.clear()
            return {"status": "success", "message": f"Done. I cleared {count} recent conversation record{'s' if count != 1 else ''}."}
        if lower in {"what recent conversations do you remember", "list recent conversations"}:
            count = len(self._conversations.list_conversations())
            return {"status": "success", "message": f"I currently retain {count} recent conversation{'s' if count != 1 else ''}, within the 20-conversation and three-day limits."}
        return None

    def cancel_confirmation(self, token: str) -> None:
        """Discard pending explicit or repeated sensitive-memory content."""
        self._pending_sensitive.pop(token, None)
        if self._episodic is not None:
            self._episodic.cancel(token)
        self._learner.cancel(token)

    def _visible_records(self):
        return [
            record for record in self._memories.list_records()
            if record.status.value == "active" and record.consent_level is MemoryConsentLevel.EXPLICIT
        ]

    def _find(self, query: str):
        terms = set(self._normalize(query).split())
        scored = []
        for record in self._visible_records():
            content = self._normalize(record.content)
            overlap = len(terms & set(content.split()))
            if content == self._normalize(query) or overlap:
                scored.append((content != self._normalize(query), -overlap, record.memory_id, record))
        return [item[3] for item in sorted(scored)]

    @staticmethod
    def _match(pattern: str, value: str) -> str | None:
        match = re.fullmatch(pattern, value.strip(), re.IGNORECASE)
        return None if match is None else match.group(1).strip()

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))

    @staticmethod
    def _looks_sensitive(value: str) -> bool:
        normalized = NaturalMemoryController._normalize(value)
        sensitive_terms = {
            "password", "passcode", "pin", "medical", "diagnosis", "health",
            "bank", "account", "salary", "income", "address", "passport",
            "social security", "credit card", "security code", "api key", "token",
        }
        return any(term in normalized for term in sensitive_terms)

    @staticmethod
    def _looks_like_style_feedback(value: str) -> bool:
        return value.startswith((
            "be more concise", "be more detailed", "be less formal", "be more formal",
            "keep your answers ", "keep your responses ", "call me ",
            "address me as ", "i prefer your answers ", "i prefer your responses ",
        ))

    def _refresh_reflections(self) -> None:
        if self._reflections is not None:
            self._reflections.refresh()
