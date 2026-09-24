"""Pure reconciliation decisions for safe travel calendar updates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum

from jarvis.travel.models import TravelSegment, TravelStatus
from jarvis.travel.store import SQLiteTravelSyncStore, TravelSyncRecord


class SyncOperation(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    NOOP = "noop"
    REVIEW = "review"
    CANCELLATION_REVIEW = "cancellation_review"


@dataclass(frozen=True, slots=True)
class SyncDecision:
    operation: SyncOperation
    reason: str
    identity: str | None = None
    calendar_event_id: str | None = None


class TravelSynchronizer:
    def __init__(self, store: SQLiteTravelSyncStore) -> None:
        self._store = store

    def plan(self, segment: TravelSegment, source_message_id: str) -> SyncDecision:
        error = segment.validation_error()
        if error:
            return SyncDecision(SyncOperation.REVIEW, error)
        if not source_message_id.strip():
            return SyncDecision(SyncOperation.REVIEW, "missing source message id")

        existing = self._store.get(segment.identity)
        if segment.status is TravelStatus.CANCELLED:
            if existing is None:
                return SyncDecision(
                    SyncOperation.REVIEW,
                    "cancellation has no matching calendar event",
                    segment.identity,
                )
            return SyncDecision(
                SyncOperation.CANCELLATION_REVIEW,
                "matched cancellation requires confirmation",
                segment.identity,
                existing.calendar_event_id,
            )
        if existing is None:
            return SyncDecision(
                SyncOperation.CREATE,
                "new booking segment",
                segment.identity,
            )
        if existing.content_hash == segment.content_hash:
            self._remember_source(existing, source_message_id)
            return SyncDecision(
                SyncOperation.NOOP,
                "duplicate or forwarded copy",
                segment.identity,
                existing.calendar_event_id,
            )
        return SyncDecision(
            SyncOperation.UPDATE,
            "existing booking segment changed",
            segment.identity,
            existing.calendar_event_id,
        )

    def record_success(
        self,
        segment: TravelSegment,
        source_message_id: str,
        calendar_event_id: str,
    ) -> None:
        if segment.validation_error():
            raise ValueError("cannot record an invalid travel segment")
        if not source_message_id.strip() or not calendar_event_id.strip():
            raise ValueError("source message and calendar event IDs are required")
        existing = self._store.get(segment.identity)
        sources = set(() if existing is None else existing.source_message_ids)
        sources.add(source_message_id)
        self._store.upsert(
            TravelSyncRecord(
                identity=segment.identity,
                content_hash=segment.content_hash,
                calendar_event_id=calendar_event_id,
                source_message_ids=tuple(sorted(sources)),
                updated_at=datetime.now(timezone.utc),
                journey_reference=(
                    segment.journey_reference or segment.booking_reference
                ),
                passenger_name=segment.passenger_name,
                segment_reference=segment.segment_reference,
            )
        )

    def _remember_source(
        self, record: TravelSyncRecord, source_message_id: str
    ) -> None:
        if source_message_id in record.source_message_ids:
            return
        self._store.upsert(
            TravelSyncRecord(
                identity=record.identity,
                content_hash=record.content_hash,
                calendar_event_id=record.calendar_event_id,
                source_message_ids=record.source_message_ids + (source_message_id,),
                updated_at=datetime.now(timezone.utc),
                journey_reference=record.journey_reference,
                passenger_name=record.passenger_name,
                segment_reference=record.segment_reference,
            )
        )
