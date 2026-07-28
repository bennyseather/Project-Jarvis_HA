"""Lifecycle, explanation, feedback, and action routing for suggestions."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from jarvis.models.home_assistant_gateway import HomeAssistantActionProposal
from jarvis.models.proactive import (
    ProactiveCandidate,
    ProactiveSuggestion,
    ProactiveSuggestionStatus,
)


class ProactiveAssistanceManager:
    def __init__(self, store, policy, detector, action_gateway=None, clock=None):
        self._store = store
        self.policy = policy
        self._detector = detector
        self._gateway = action_gateway
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._current_by_conversation: dict[str, str] = {}

    def set_action_gateway(self, gateway) -> None:
        self._gateway = gateway

    def refresh(self, *, states=(), timeline_events=(), reflections=()):
        now = self._clock()
        self._expire(now)
        if not self.policy.enabled:
            return ()
        candidates = self._detector.detect(
            states=states,
            timeline_events=timeline_events,
            reflections=reflections,
        )
        pending_subjects = {
            record.subject: record
            for record in self._store.list_records()
            if record.status in {
                ProactiveSuggestionStatus.PENDING,
                ProactiveSuggestionStatus.SNOOZED,
            }
        }
        for candidate in candidates:
            if not self.policy.permits_candidate(
                candidate, suppressed=self._store.is_suppressed(candidate.subject)
            ):
                continue
            existing = pending_subjects.get(candidate.subject)
            identifier = hashlib.sha256(candidate.subject.encode()).hexdigest()[:24]
            previous = self._store.get(identifier)
            if (
                existing is None
                and previous is not None
                and previous.status is not ProactiveSuggestionStatus.EXPIRED
                and previous.updated_at + timedelta(
                    minutes=self.policy.cooldown_minutes
                ) > now
            ):
                continue
            suggestion = self._suggestion(candidate, existing, now)
            self._store.upsert(suggestion)
        self._bound_pending()
        return self.pending()

    def pending(self) -> tuple[ProactiveSuggestion, ...]:
        now = self._clock()
        return tuple(sorted(
            (
                record for record in self._store.list_records()
                if record.status is ProactiveSuggestionStatus.PENDING
                or (
                    record.status is ProactiveSuggestionStatus.SNOOZED
                    and record.snoozed_until is not None
                    and record.snoozed_until <= now
                )
            ),
            key=lambda item: (-item.confidence, item.created_at, item.suggestion_id),
        ))[:self.policy.maximum_pending]

    def attention(self, conversation_id: str) -> dict[str, object]:
        records = self.pending()
        if not records:
            return {"status": "success", "message": "Nothing currently needs your attention."}
        self._current_by_conversation[conversation_id] = records[0].suggestion_id
        details = "; ".join(record.message for record in records[:5])
        suffix = "" if len(records) <= 5 else f" {len(records) - 5} more are pending."
        return {
            "status": "success",
            "message": f"{len(records)} suggestions: {details}.{suffix}",
            "suggestion_ids": tuple(record.suggestion_id for record in records),
        }

    def explain_current(self, conversation_id: str) -> dict[str, object]:
        record = self._current(conversation_id)
        if record is None:
            return {
                "status": "clarification_required",
                "message": "Ask what needs your attention first, or name a pending suggestion.",
            }
        return {
            "status": "success",
            "message": f"I suggested that because {record.reason}",
            "suggestion_id": record.suggestion_id,
        }

    def snooze_current(self, conversation_id: str) -> dict[str, object]:
        record = self._current(conversation_id)
        if record is None:
            return self._missing()
        now = self._clock()
        self._store.upsert(replace(
            record,
            status=ProactiveSuggestionStatus.SNOOZED,
            snoozed_until=now + timedelta(minutes=self.policy.snooze_minutes),
            updated_at=now,
        ))
        return {"status": "success", "message": "Understood. I will leave that for now."}

    def suppress_current(self, conversation_id: str) -> dict[str, object]:
        record = self._current(conversation_id)
        if record is None:
            return self._missing()
        now = self._clock()
        self._store.suppress(record.subject, now)
        self._store.delete(record.suggestion_id)
        self._current_by_conversation.pop(conversation_id, None)
        return {
            "status": "success",
            "message": "Understood. I will not suggest that again.",
        }

    def clear_pending(self) -> dict[str, object]:
        count = 0
        now = self._clock()
        for record in self._store.list_records():
            if record.status in {
                ProactiveSuggestionStatus.PENDING,
                ProactiveSuggestionStatus.SNOOZED,
            }:
                self._store.upsert(replace(
                    record,
                    status=ProactiveSuggestionStatus.CLEARED,
                    updated_at=now,
                ))
                count += 1
        self._current_by_conversation.clear()
        return {"status": "success", "message": f"Cleared {count} pending suggestions."}

    def show_suppressions(self) -> dict[str, object]:
        subjects = self._store.suppressions()
        if not subjects:
            return {"status": "success", "message": "No suggestion topics are suppressed."}
        return {
            "status": "success",
            "message": "Suppressed suggestion topics: " + "; ".join(subjects),
        }

    def clear_suppressions(self) -> dict[str, object]:
        count = len(self._store.suppressions())
        self._store.clear_suppressions()
        return {
            "status": "success",
            "message": f"Removed {count} suggestion suppressions.",
        }

    async def accept_current(self, conversation_id: str) -> dict[str, object]:
        record = self._current(conversation_id)
        if record is None:
            return self._missing()
        if record.action is None:
            return {
                "status": "success",
                "message": (
                    "That suggestion is informational and has no automatic action. "
                    "No Home Assistant changes were made."
                ),
            }
        if self._gateway is None:
            return {"status": "not_supported", "message": "Home Assistant actions are unavailable."}
        try:
            proposal = HomeAssistantActionProposal(**dict(record.action))
        except (TypeError, ValueError):
            return {"status": "forbidden", "reason_code": "invalid_suggestion_action"}
        result = self._gateway.request(proposal)
        if result.get("status") == "immediate_action":
            result = await self._gateway.execute_immediate(proposal)
        elif result.get("status") == "requires_confirmation":
            result["action_payload"] = dict(record.action)
        if result.get("status") == "success":
            now = self._clock()
            self._store.upsert(replace(
                record,
                status=ProactiveSuggestionStatus.ACCEPTED,
                updated_at=now,
            ))
        return result

    def context_for(self, query: str, limit: int = 3):
        terms = set(query.casefold().split())
        ranked = []
        for record in self.pending():
            overlap = len(terms & set(
                (record.subject + " " + record.message).casefold().split()
            ))
            ranked.append((-overlap, -record.confidence, record.suggestion_id, record))
        return tuple({
            "suggestion_id": item[3].suggestion_id,
            "kind": item[3].kind.value,
            "message": item[3].message,
            "confidence": item[3].confidence,
        } for item in sorted(ranked)[:limit])

    def mark_delivered(self, suggestion_id: str, channel: str) -> None:
        record = self._store.get(suggestion_id)
        if record is None or channel in record.delivered_channels:
            return
        self._store.upsert(replace(
            record,
            delivered_channels=tuple(sorted((*record.delivered_channels, channel))),
            updated_at=self._clock(),
        ))

    def _suggestion(self, candidate, existing, now):
        identifier = hashlib.sha256(candidate.subject.encode()).hexdigest()[:24]
        return ProactiveSuggestion(
            suggestion_id=identifier,
            kind=candidate.kind,
            subject=candidate.subject,
            message=candidate.message,
            reason=candidate.reason,
            confidence=float(candidate.confidence),
            source_ids=tuple(candidate.source_ids),
            sensitive=candidate.sensitive,
            action=None if candidate.action is None else dict(candidate.action),
            status=(
                existing.status
                if existing is not None
                else ProactiveSuggestionStatus.PENDING
            ),
            created_at=existing.created_at if existing is not None else now,
            updated_at=now,
            expires_at=now + timedelta(hours=self.policy.expiry_hours),
            snoozed_until=(
                existing.snoozed_until if existing is not None else None
            ),
            delivered_channels=(
                existing.delivered_channels if existing is not None else ()
            ),
        )

    def _expire(self, now):
        for record in self._store.list_records():
            if (
                record.status in {
                    ProactiveSuggestionStatus.PENDING,
                    ProactiveSuggestionStatus.SNOOZED,
                }
                and record.expires_at <= now
            ):
                self._store.upsert(replace(
                    record,
                    status=ProactiveSuggestionStatus.EXPIRED,
                    updated_at=now,
                ))

    def _bound_pending(self):
        records = sorted(
            (
                record for record in self._store.list_records()
                if record.status in {
                    ProactiveSuggestionStatus.PENDING,
                    ProactiveSuggestionStatus.SNOOZED,
                }
            ),
            key=lambda item: (-item.confidence, item.created_at, item.suggestion_id),
        )
        for record in records[self.policy.maximum_pending:]:
            self._store.delete(record.suggestion_id)

    def _current(self, conversation_id):
        identifier = self._current_by_conversation.get(conversation_id)
        if identifier is not None:
            record = self._store.get(identifier)
            if record is not None:
                return record
        records = self.pending()
        if not records:
            return None
        self._current_by_conversation[conversation_id] = records[0].suggestion_id
        return records[0]

    @staticmethod
    def _missing():
        return {
            "status": "clarification_required",
            "message": "There is no current suggestion to apply.",
        }
