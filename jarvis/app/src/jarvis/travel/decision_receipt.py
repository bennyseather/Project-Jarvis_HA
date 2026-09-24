"""Validated human decisions for itineraries without a provider order number."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from jarvis.travel.berg_hansen_parser import parse_berg_hansen_html
from jarvis.travel.models import TravelSegment
from jarvis.travel.store import SQLiteTravelSyncStore
from jarvis.travel.synchronizer import SyncDecision, SyncOperation, TravelSynchronizer


class TravelDecisionAction(StrEnum):
    ADD = "add"
    REPLACE = "replace"
    IGNORE = "ignore"


@dataclass(frozen=True, slots=True)
class TravelDecisionReceipt:
    approval_id: str
    source_message_id: str
    passenger_name: str
    approver_email: str
    action: TravelDecisionAction
    replacement_order_number: str = ""

    def validation_error(self) -> str | None:
        if not self.approval_id.strip():
            return "missing approval id"
        if not self.source_message_id.strip():
            return "missing source message id"
        if not self.passenger_name.strip():
            return "missing passenger name"
        if not self.approver_email.strip():
            return "missing approver email"
        if self.action is TravelDecisionAction.REPLACE:
            value = self.replacement_order_number.strip()
            if not value:
                return "replacement requires an existing order number"
            if not value.isdigit():
                return "replacement order number must contain digits only"
        return None


@dataclass(frozen=True, slots=True)
class DryRunItem:
    operation: SyncOperation
    reason: str
    identity: str | None
    calendar_event_id: str | None
    segment_reference: str = ""


@dataclass(frozen=True, slots=True)
class TravelDecisionDryRun:
    action: TravelDecisionAction
    journey_reference: str | None
    items: tuple[DryRunItem, ...]
    ignored: bool = False


class TravelDecisionReconciler:
    """Turns an approval receipt into a non-mutating reconciliation report."""

    def __init__(self, store: SQLiteTravelSyncStore) -> None:
        self._store = store
        self._synchronizer = TravelSynchronizer(store)

    def dry_run(
        self, html: str, receipt: TravelDecisionReceipt
    ) -> TravelDecisionDryRun:
        error = receipt.validation_error()
        if error:
            raise ValueError(error)
        if receipt.action is TravelDecisionAction.IGNORE:
            return TravelDecisionDryRun(receipt.action, None, (), ignored=True)

        parsed = parse_berg_hansen_html(html)
        actual_passengers = {item.passenger_name for item in parsed}
        if actual_passengers != {receipt.passenger_name}:
            raise ValueError("approval passenger does not match itinerary")

        if receipt.action is TravelDecisionAction.REPLACE:
            journey_reference = receipt.replacement_order_number.strip()
            previous = self._store.list_by_journey_reference(
                journey_reference, receipt.passenger_name
            )
            if not previous:
                raise ValueError("replacement order number was not found")
        else:
            journey_reference = f"MANUAL:{receipt.approval_id.strip()}"
            previous = ()

        segments: tuple[TravelSegment, ...] = tuple(
            replace(segment, journey_reference=journey_reference)
            for segment in parsed
        )
        items = [
            self._item(
                self._synchronizer.plan(segment, receipt.source_message_id),
                segment.segment_reference,
            )
            for segment in segments
        ]

        current_identities = {segment.identity for segment in segments}
        for record in previous:
            if record.identity not in current_identities:
                items.append(
                    DryRunItem(
                        SyncOperation.CANCELLATION_REVIEW,
                        "existing journey segment omitted from replacement",
                        record.identity,
                        record.calendar_event_id,
                        record.segment_reference,
                    )
                )
        return TravelDecisionDryRun(
            receipt.action, journey_reference, tuple(items)
        )

    @staticmethod
    def _item(decision: SyncDecision, segment_reference: str) -> DryRunItem:
        return DryRunItem(
            decision.operation,
            decision.reason,
            decision.identity,
            decision.calendar_event_id,
            segment_reference,
        )
