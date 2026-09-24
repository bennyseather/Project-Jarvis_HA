"""Normalized travel records independent of email and calendar providers."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class TravelStatus(StrEnum):
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


def _normal(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


@dataclass(frozen=True, slots=True)
class TravelSegment:
    booking_reference: str
    passenger_name: str
    segment_reference: str
    segment_type: str
    origin: str
    destination: str
    starts_at: datetime
    ends_at: datetime
    title: str
    location: str = ""
    details: str = ""
    status: TravelStatus = TravelStatus.CONFIRMED
    journey_reference: str = ""

    def validation_error(self) -> str | None:
        if not self.booking_reference.strip():
            return "missing booking reference"
        if not self.passenger_name.strip():
            return "missing passenger name"
        if not self.segment_reference.strip():
            return "missing stable segment reference"
        if self.starts_at.tzinfo is None or self.starts_at.utcoffset() is None:
            return "segment start is missing a timezone"
        if self.ends_at.tzinfo is None or self.ends_at.utcoffset() is None:
            return "segment end is missing a timezone"
        if self.ends_at <= self.starts_at:
            return "segment end must be after its start"
        return None

    @property
    def identity(self) -> str:
        """Stable across forwarded copies and itinerary time corrections."""
        source = "|".join(
            _normal(value)
            for value in (
                self.journey_reference or self.booking_reference,
                self.passenger_name,
                self.segment_reference,
            )
        )
        return hashlib.sha256(source.encode("utf-8")).hexdigest()

    @property
    def content_hash(self) -> str:
        payload = {
            "segment_type": _normal(self.segment_type),
            "origin": _normal(self.origin),
            "destination": _normal(self.destination),
            "starts_at": self.starts_at.isoformat(),
            "ends_at": self.ends_at.isoformat(),
            "title": self.title.strip(),
            "location": self.location.strip(),
            "details": self.details.strip(),
            "status": self.status.value,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
