"""Airport-local time resolution for itinerary timestamps.

The email times are interpreted in the airport's named timezone. Named zones
are required instead of fixed UTC offsets so daylight-saving rules are applied
for the actual travel date.
"""

from datetime import date, datetime, time
from zoneinfo import ZoneInfo


# Deliberately explicit and reviewable. Add airports observed in approved
# itineraries; unknown codes must be held for review instead of guessed.
AIRPORT_TIMEZONES: dict[str, str] = {
    "AMS": "Europe/Amsterdam",
    "BGO": "Europe/Oslo",
    "CPH": "Europe/Copenhagen",
    "DXB": "Asia/Dubai",
    "FRA": "Europe/Berlin",
    "HAU": "Europe/Oslo",
    "HOV": "Europe/Oslo",
    "IST": "Europe/Istanbul",
    "LHR": "Europe/London",
    "OSL": "Europe/Oslo",
    "SVG": "Europe/Oslo",
}


class UnknownAirportTimezone(ValueError):
    """Raised when an airport cannot safely be assigned a named timezone."""


def airport_timezone(airport_code: str) -> ZoneInfo:
    code = airport_code.strip().upper()
    try:
        return ZoneInfo(AIRPORT_TIMEZONES[code])
    except KeyError as exc:
        raise UnknownAirportTimezone(
            f"timezone is not configured for airport {code or '<missing>'}"
        ) from exc


def resolve_flight_times(
    departure_airport: str,
    departure_date: date,
    departure_time: time,
    arrival_airport: str,
    arrival_date: date,
    arrival_time: time,
) -> tuple[datetime, datetime]:
    """Resolve itinerary-local departure and arrival into aware datetimes."""

    return (
        datetime.combine(
            departure_date,
            departure_time,
            tzinfo=airport_timezone(departure_airport),
        ),
        datetime.combine(
            arrival_date,
            arrival_time,
            tzinfo=airport_timezone(arrival_airport),
        ),
    )
