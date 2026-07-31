"""Bounded episodic conversation summaries without transcript retention."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from secrets import token_urlsafe

from jarvis.models.memory import (
    MemoryConsentLevel,
    MemoryRecordFactory,
    MemorySource,
    MemoryStatus,
    MemoryType,
)


@dataclass(frozen=True, slots=True)
class EpisodicPolicy:
    enabled: bool = True
    retention_days: int = 30
    maximum_episodes: int = 50
    minimum_messages: int = 6
    context_limit: int = 3

    @classmethod
    def from_config(cls, value):
        config = {} if value is None else value
        if not isinstance(config, dict):
            raise ValueError("episodic_memory must be a mapping")
        values = {
            "enabled": config.get("enabled", True),
            "retention_days": config.get("retention_days", 30),
            "maximum_episodes": config.get("maximum_episodes", 50),
            "minimum_messages": config.get("minimum_messages", 6),
            "context_limit": config.get("context_limit", 3),
        }
        if not isinstance(values["enabled"], bool):
            raise ValueError("episodic_memory.enabled must be a boolean")
        for name, minimum, maximum in (
            ("retention_days", 1, 365),
            ("maximum_episodes", 1, 200),
            ("minimum_messages", 4, 50),
            ("context_limit", 1, 10),
        ):
            value = values[name]
            if not isinstance(value, int) or isinstance(value, bool) or not minimum <= value <= maximum:
                raise ValueError(f"episodic_memory.{name} must be between {minimum} and {maximum}")
        return cls(**values)


class EpisodicMemoryManager:
    TAG = "jarvis:episode"
    _COMMAND_PREFIXES = (
        "what were we discussing", "what did we decide", "show recent conversations",
        "remember this conversation", "pin this conversation", "forget this conversation",
        "forget conversations about", "clear conversation history",
    )
    _SENSITIVE = {
        "password", "passcode", "pin", "medical", "diagnosis", "health",
        "bank", "salary", "income", "passport", "credit card", "api key",
        "security code", "token", "secret",
    }
    _STOP = {
        "about", "after", "again", "also", "and", "are", "but", "can", "could",
        "did", "for", "from", "have", "how", "into", "jarvis", "just", "like",
        "please", "that", "the", "this", "to", "was", "we", "what", "when",
        "where", "which", "with", "would", "you", "your",
    }

    def __init__(self, memory_store, conversation_store, policy, *, reasoning=None, clock=None, factory=None):
        self._memories = memory_store
        self._conversations = conversation_store
        self.policy = policy
        self._reasoning = reasoning
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._factory = factory or MemoryRecordFactory(timestamp_factory=self._clock)
        self._pending: dict[str, tuple[str, bool]] = {}
        self.prune()

    def handle(self, text, conversation_id):
        raw = text.strip()
        lower = " ".join(raw.casefold().strip(" .?!").split())
        if lower == "what were we discussing":
            records = self._episodes()
            if not records:
                return {"status": "success", "message": "I have no durable conversation summaries."}
            return {"status": "success", "message": records[-1].content}
        match = re.fullmatch(r"what did we decide about (.+)", raw, re.IGNORECASE)
        if match:
            records = self._matching(match.group(1))
            return {
                "status": "success",
                "message": records[-1].content if records else "I found no matching conversation decision.",
            }
        if lower == "show recent conversations":
            records = self._episodes()[-10:]
            if not records:
                return {"status": "success", "message": "No durable conversation summaries are stored."}
            lines = [f"- {record.updated_at.date().isoformat()}: {record.content}" for record in reversed(records)]
            return {"status": "success", "message": "Recent conversation summaries:\n" + "\n".join(lines)}
        if lower in {"remember this conversation", "pin this conversation"}:
            pinned = lower.startswith("pin ")
            return self._remember(conversation_id, pinned=pinned)
        if lower == "forget this conversation":
            deleted = self._delete_where(lambda record: record.metadata.get("conversation_id") == self._id(conversation_id))
            return {"status": "success", "message": f"Permanently deleted {deleted} conversation summar{'y' if deleted == 1 else 'ies'}."}
        match = re.fullmatch(r"forget conversations about (.+)", raw, re.IGNORECASE)
        if match:
            identifiers = {record.memory_id for record in self._matching(match.group(1))}
            deleted = self._delete_where(lambda record: record.memory_id in identifiers)
            return {"status": "success", "message": f"Permanently deleted {deleted} matching conversation summar{'y' if deleted == 1 else 'ies'}."}
        if lower == "clear conversation history":
            deleted = self._delete_where(lambda record: True)
            recent = self._conversations.clear()
            return {"status": "success", "message": f"Permanently cleared {deleted} summaries and {recent} recent conversation records."}
        return None

    def confirm(self, token):
        pending = self._pending.pop(token, None)
        if pending is None:
            return None
        conversation_id, pinned = pending
        return self._create(conversation_id, pinned=pinned, sensitive=True)

    def cancel(self, token):
        self._pending.pop(token, None)

    def observe(self, conversation_id):
        if not self.policy.enabled:
            return
        self.prune()
        identifier = self._id(conversation_id)
        messages = self._eligible_messages(identifier)
        if len(messages) < self.policy.minimum_messages or self._is_sensitive(messages):
            return
        existing = [record for record in self._episodes() if record.metadata.get("conversation_id") == identifier]
        if existing:
            return
        self._create(identifier, automatic=True)

    @classmethod
    def is_command(cls, text):
        return cls._is_command(text)

    def prune(self):
        now = self._clock()
        records = self._episodes(include_expired=True)
        for record in records:
            if record.expires_at is not None and record.expires_at <= now:
                self._memories.delete(record.memory_id)
        unpinned = [record for record in self._episodes() if not record.metadata.get("pinned", False)]
        excess = max(0, len(self._episodes()) - self.policy.maximum_episodes)
        for record in unpinned[:excess]:
            self._memories.delete(record.memory_id)

    def _remember(self, conversation_id, *, pinned):
        messages = self._eligible_messages(conversation_id)
        if len(messages) < 2:
            return {"status": "clarification_required", "message": "There is not enough conversation to summarise yet."}
        if self._is_sensitive(messages):
            token = token_urlsafe(12)
            self._pending[token] = (self._id(conversation_id), pinned)
            return {
                "status": "requires_confirmation",
                "message": "This conversation may contain sensitive information. Confirm to store a private summary.",
                "confirmation_token": token,
            }
        return self._create(conversation_id, pinned=pinned)

    def _create(self, conversation_id, *, pinned=False, sensitive=False, automatic=False):
        identifier = self._id(conversation_id)
        messages = self._eligible_messages(identifier)
        summary = self._redact_credentials(
            self._summary(messages, use_reasoning=not automatic)
        )
        if not summary:
            return {"status": "unavailable", "message": "I could not create a useful conversation summary."}
        current = self._episodes()
        if len(current) >= self.policy.maximum_episodes:
            removable = next(
                (record for record in current if not record.metadata.get("pinned", False)),
                None,
            )
            if removable is None:
                return {
                    "status": "clarification_required",
                    "message": "The pinned conversation-summary limit is full. Forget one before storing another.",
                }
            self._memories.delete(removable.memory_id)
        expires = None if pinned else self._clock() + timedelta(days=self.policy.retention_days)
        consent = (
            MemoryConsentLevel.SENSITIVE_CONFIRMED if sensitive else
            MemoryConsentLevel.AUTOMATIC_LOW_SENSITIVITY if automatic else
            MemoryConsentLevel.EXPLICIT
        )
        record = self._factory.create(
            MemoryType.CONVERSATION_SUMMARY,
            summary[:800],
            MemorySource.CONVERSATION_SUMMARY,
            consent,
            expires_at=expires,
            importance=0.8 if pinned else 0.6,
            confidence=0.8,
            tags=(self.TAG,) + tuple(self._topics(messages)[:5]),
            metadata={
                "conversation_id": identifier,
                "pinned": pinned,
                "automatic": automatic,
                "sensitive": sensitive,
                "message_count": len(messages),
            },
        )
        self._memories.create(record)
        self.prune()
        qualifier = "pinned" if pinned else "stored"
        return {"status": "success", "message": f"Conversation summary {qualifier}."}

    def _summary(self, messages, *, use_reasoning):
        topics = self._topics(messages)
        fallback = "Conversation topics: " + ", ".join(topics[:8]) + "."
        decisions = any(re.search(r"\b(agree|agreed|decide|decided|plan|prefer|will|should)\b", message.content, re.I) for message in messages if message.role == "user")
        if decisions:
            fallback += " The conversation included an explicit preference, plan, or decision."
        if not use_reasoning or self._reasoning is None:
            return fallback
        transcript = "\n".join(f"{message.role}: {message.content[:600]}" for message in messages[-12:])
        result = self._reasoning.reason(
            instructions=(
                "Create a factual conversation summary in at most 90 words. Preserve useful "
                "decisions and unresolved next steps. Do not quote the transcript, include "
                "credentials, infer emotions, or add facts. Return summary text only."
            ),
            input_messages=[{"role": "user", "content": transcript}],
            model="gpt-5.6-luna",
            timeout_seconds=20,
        )
        return str(result.get("message", fallback)).strip() if result.get("status") == "success" else fallback

    def _eligible_messages(self, conversation_id):
        messages = self._conversations.history(conversation_id, min(50, self._conversations._maximum_messages))
        return tuple(message for message in messages if not self._is_command(message.content))

    def _topics(self, messages):
        words = []
        for message in messages:
            if message.role != "user":
                continue
            words.extend(word for word in re.findall(r"[a-z0-9]+", message.content.casefold()) if len(word) > 2 and word not in self._STOP)
        return [word for word, _ in Counter(words).most_common(12)] or ["general assistance"]

    def _is_sensitive(self, messages):
        text = " ".join(message.content.casefold() for message in messages)
        return any(
            re.search(rf"\b{re.escape(term)}\b", text) is not None
            for term in self._SENSITIVE
        )

    def _episodes(self, *, include_expired=False):
        now = self._clock()
        records = [
            record for record in self._memories.list_records()
            if self.TAG in record.tags and record.status is MemoryStatus.ACTIVE
            and (include_expired or record.expires_at is None or record.expires_at > now)
        ]
        return sorted(records, key=lambda record: (record.updated_at, record.memory_id))

    def _matching(self, query):
        terms = set(re.findall(r"[a-z0-9]+", query.casefold()))
        return [record for record in self._episodes() if terms & set(re.findall(r"[a-z0-9]+", (record.content + " " + " ".join(record.tags)).casefold()))]

    def _delete_where(self, predicate):
        records = [record for record in self._episodes(include_expired=True) if predicate(record)]
        for record in records:
            self._memories.delete(record.memory_id)
        return len(records)

    @classmethod
    def _is_command(cls, text):
        normalized = " ".join(text.casefold().strip(" .?!").split())
        return normalized.startswith(cls._COMMAND_PREFIXES) or normalized.startswith("confirm memory ")

    def _id(self, conversation_id):
        return self._conversations.normalize_conversation_id(conversation_id)

    @staticmethod
    def _redact_credentials(value):
        return re.sub(
            r"\b(password|passcode|api key|security code|secret)\b\s*(?:is|:|=)\s*\S+",
            r"\1 [redacted]",
            str(value),
            flags=re.IGNORECASE,
        )
