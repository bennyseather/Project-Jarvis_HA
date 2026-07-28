"""Deterministic reflection over approved durable memories."""

from __future__ import annotations

import hashlib
import re
from dataclasses import replace
from datetime import datetime, timezone

from jarvis.models.memory import MemoryConsentLevel, MemoryStatus
from jarvis.models.reflection import ReflectionKind, ReflectionRecord


class ReflectiveLearningManager:
    """Build bounded, inspectable relationships without persisting raw inference."""

    _MAX_REFLECTIONS = 500
    _STOP_WORDS = {
        "a", "an", "and", "at", "be", "i", "in", "is", "it", "my", "of",
        "on", "that", "the", "to", "user", "prefers", "prefer", "likes",
    }
    _STYLE_WORDS = {
        "answer", "answers", "call", "concise", "detailed", "formal", "name",
        "reply", "response", "short", "style", "tone",
    }

    def __init__(self, memory_store, reflection_store, clock=None) -> None:
        self._memories = memory_store
        self._reflections = reflection_store
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def refresh(self) -> None:
        """Rebuild reflections so corrections and hard deletion leave no history."""
        self._consolidate_exact_duplicates()
        memories = tuple(
            record for record in self._memories.list_records()
            if record.status is MemoryStatus.ACTIVE
        )
        previous = {
            record.reflection_id: record for record in self._reflections.list_records()
        }
        generated: list[ReflectionRecord] = []

        by_subject: dict[str, list] = {}
        for memory in memories:
            subject = str(memory.metadata.get("candidate_key", "")).strip()
            if subject:
                by_subject.setdefault(subject, []).append(memory)
            if self._is_style(memory):
                generated.append(self._record(
                    ReflectionKind.STYLE,
                    f"style:{memory.memory_id}",
                    memory.content,
                    (memory,),
                    previous,
                ))
            if memory.confidence is not None and memory.confidence < 0.75:
                generated.append(self._record(
                    ReflectionKind.UNCERTAINTY,
                    f"uncertain:{memory.memory_id}",
                    f"This remembered information has limited confidence: {memory.content}",
                    (memory,),
                    previous,
                    confidence=memory.confidence,
                ))
                generated.append(self._record(
                    ReflectionKind.FOLLOW_UP,
                    f"follow-up:uncertain:{memory.memory_id}",
                    f"Ask the user to confirm when relevant: {memory.content}",
                    (memory,),
                    previous,
                    confidence=memory.confidence,
                ))

        for subject, related in sorted(by_subject.items()):
            contents = {" ".join(item.content.casefold().split()) for item in related}
            if len(contents) > 1:
                generated.append(self._record(
                    ReflectionKind.CONTRADICTION,
                    f"contradiction:{subject}",
                    "Conflicting remembered information: "
                    + "; ".join(item.content for item in related),
                    tuple(related),
                    previous,
                    confidence=0.5,
                ))
                generated.append(self._record(
                    ReflectionKind.FOLLOW_UP,
                    f"follow-up:contradiction:{subject}",
                    f"Ask the user to resolve this conflict when relevant: {subject}",
                    tuple(related),
                    previous,
                    confidence=0.5,
                ))

        for index, left in enumerate(memories):
            for right in memories[index + 1:]:
                shared = self._terms(left.content) & self._terms(right.content)
                if not shared:
                    continue
                subject = "relation:" + ":".join(sorted(
                    (left.memory_id, right.memory_id)
                ))
                generated.append(self._record(
                    ReflectionKind.RELATION,
                    subject,
                    f"Related remembered information: {left.content}; {right.content}",
                    (left, right),
                    previous,
                    confidence=min(
                        left.confidence if left.confidence is not None else 1.0,
                        right.confidence if right.confidence is not None else 1.0,
                    ),
                ))

        priority = {
            ReflectionKind.CONTRADICTION: 0,
            ReflectionKind.UNCERTAINTY: 1,
            ReflectionKind.STYLE: 2,
            ReflectionKind.FOLLOW_UP: 3,
            ReflectionKind.RELATION: 4,
        }
        bounded = sorted(
            generated,
            key=lambda record: (
                priority[record.kind],
                record.subject,
                record.reflection_id,
            ),
        )[:self._MAX_REFLECTIONS]
        self._reflections.replace_all(tuple(bounded))

    def context_for(self, query: str, limit: int = 5) -> tuple[dict[str, object], ...]:
        terms = self._terms(query)
        ranked = []
        for record in self._reflections.list_records():
            if record.sensitive:
                continue
            overlap = len(terms & self._terms(record.content + " " + record.subject))
            if overlap or record.kind is ReflectionKind.STYLE:
                ranked.append((-overlap, record.kind.value, record.reflection_id, record))
        return tuple({
            "kind": item[3].kind.value,
            "content": item[3].content,
            "confidence": item[3].confidence,
        } for item in sorted(ranked)[:limit])

    def uncertainties(self) -> tuple[ReflectionRecord, ...]:
        return tuple(
            record for record in self._reflections.list_records()
            if record.kind in {ReflectionKind.UNCERTAINTY, ReflectionKind.CONTRADICTION}
            and not record.sensitive
        )

    def connected_memory_ids(self, memory_ids) -> frozenset[str]:
        connected = set(memory_ids)
        changed = True
        records = self._reflections.list_records()
        while changed:
            changed = False
            for record in records:
                sources = set(record.source_memory_ids)
                if sources & connected and not sources <= connected:
                    connected.update(sources)
                    changed = True
        return frozenset(connected)

    def records(self) -> tuple[ReflectionRecord, ...]:
        return self._reflections.list_records()

    def _consolidate_exact_duplicates(self) -> None:
        grouped: dict[tuple, list] = {}
        for memory in self._memories.list_records():
            if memory.status is not MemoryStatus.ACTIVE:
                continue
            key = (
                " ".join(memory.content.casefold().split()),
                memory.memory_type,
                memory.consent_level,
            )
            grouped.setdefault(key, []).append(memory)
        for duplicates in grouped.values():
            if len(duplicates) < 2:
                continue
            ordered = sorted(
                duplicates, key=lambda item: (item.created_at, item.memory_id)
            )
            keeper = ordered[0]
            conversations = {
                conversation_id
                for item in ordered
                for conversation_id in item.metadata.get(
                    "source_conversation_ids", ()
                )
                if isinstance(conversation_id, str)
            }
            metadata = dict(keeper.metadata)
            if conversations:
                metadata["source_conversation_ids"] = sorted(conversations)
            self._memories.update(replace(
                keeper,
                updated_at=self._clock(),
                tags=tuple(sorted({
                    tag for item in ordered for tag in item.tags
                })),
                metadata=metadata,
            ))
            for duplicate in ordered[1:]:
                self._memories.delete(duplicate.memory_id)

    def _record(
        self, kind, subject, content, memories, previous, *, confidence=1.0
    ) -> ReflectionRecord:
        source_ids = tuple(sorted(memory.memory_id for memory in memories))
        identifier = hashlib.sha256(
            f"{kind.value}|{subject}|{'|'.join(source_ids)}".encode()
        ).hexdigest()[:24]
        now = self._clock()
        existing = previous.get(identifier)
        conversations = tuple(sorted({
            conversation_id
            for memory in memories
            for conversation_id in memory.metadata.get("source_conversation_ids", ())
            if isinstance(conversation_id, str)
        }))
        sensitive = any(
            memory.consent_level is MemoryConsentLevel.SENSITIVE_CONFIRMED
            for memory in memories
        )
        return ReflectionRecord(
            identifier, kind, subject, content, float(confidence), source_ids,
            conversations, sensitive, existing.created_at if existing else now, now,
        )

    def _is_style(self, memory) -> bool:
        return (
            "style_preference" in memory.tags
            or bool(self._terms(memory.content) & self._STYLE_WORDS)
        )

    @classmethod
    def _terms(cls, value: str) -> set[str]:
        return {
            word for word in re.findall(r"[a-z0-9]+", value.casefold())
            if len(word) > 2 and word not in cls._STOP_WORDS
        }
