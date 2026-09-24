"""Provider-neutral construction of Microsoft Graph calendar event fields."""

from datetime import datetime
from zoneinfo import ZoneInfo

from jarvis.travel.models import TravelSegment


def _graph_datetime(value: datetime) -> dict[str, str]:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("calendar timestamps must be timezone-aware")
    if not isinstance(value.tzinfo, ZoneInfo):
        raise ValueError("calendar timestamps must use a named IANA timezone")
    return {
        "dateTime": value.replace(tzinfo=None).isoformat(timespec="seconds"),
        "timeZone": value.tzinfo.key,
    }


def graph_event_payload(segment: TravelSegment) -> dict[str, object]:
    """Preserve independent local timezones for event start and event end."""

    error = segment.validation_error()
    if error:
        raise ValueError(error)
    return {
        "subject": segment.title,
        "start": _graph_datetime(segment.starts_at),
        "end": _graph_datetime(segment.ends_at),
        "location": {"displayName": segment.location},
        "body": {"contentType": "text", "content": segment.details},
        "showAs": "busy",
    }
