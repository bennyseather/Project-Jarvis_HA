"""Guarded relay-to-calendar processing independent of Microsoft transport."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from jarvis.travel.berg_hansen_parser import parse_berg_hansen_html
from jarvis.travel.models import TravelSegment
from jarvis.travel.synchronizer import SyncDecision, SyncOperation, TravelSynchronizer


class CalendarWriter(Protocol):
    def find_existing(self, segment: TravelSegment) -> str | None: ...
    def create(self, segment: TravelSegment) -> str: ...
    def update(self, event_id: str, segment: TravelSegment) -> None: ...


@dataclass(frozen=True, slots=True)
class ProcessingResult:
    segment: TravelSegment
    decision: SyncDecision
    calendar_event_id: str | None = None
    adopted_existing: bool = False


class TravelRelayProcessor:
    def __init__(
        self,
        synchronizer: TravelSynchronizer,
        calendar: CalendarWriter,
    ) -> None:
        self._synchronizer = synchronizer
        self._calendar = calendar

    def process_html(
        self,
        html: str,
        source_message_id: str,
        *,
        write_enabled: bool = False,
    ) -> list[ProcessingResult]:
        results: list[ProcessingResult] = []
        for segment in parse_berg_hansen_html(html):
            decision = self._synchronizer.plan(segment, source_message_id)
            if not write_enabled or decision.operation in {
                SyncOperation.NOOP,
                SyncOperation.REVIEW,
                SyncOperation.CANCELLATION_REVIEW,
            }:
                results.append(
                    ProcessingResult(segment, decision, decision.calendar_event_id)
                )
                continue

            if decision.operation is SyncOperation.CREATE:
                existing_event_id = self._calendar.find_existing(segment)
                if existing_event_id:
                    self._synchronizer.record_success(
                        segment, source_message_id, existing_event_id
                    )
                    results.append(
                        ProcessingResult(
                            segment,
                            SyncDecision(
                                SyncOperation.NOOP,
                                "adopted existing pilot event",
                                segment.identity,
                                existing_event_id,
                            ),
                            existing_event_id,
                            adopted_existing=True,
                        )
                    )
                    continue
                event_id = self._calendar.create(segment)
                self._synchronizer.record_success(
                    segment, source_message_id, event_id
                )
                results.append(ProcessingResult(segment, decision, event_id))
                continue

            if decision.operation is SyncOperation.UPDATE:
                if not decision.calendar_event_id:
                    raise RuntimeError("update decision is missing an event ID")
                self._calendar.update(decision.calendar_event_id, segment)
                self._synchronizer.record_success(
                    segment, source_message_id, decision.calendar_event_id
                )
                results.append(
                    ProcessingResult(
                        segment, decision, decision.calendar_event_id
                    )
                )
                continue

            raise RuntimeError(f"unsupported write operation: {decision.operation}")
        return results
