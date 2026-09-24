"""Explicit normalization policies for travel itinerary data."""

from datetime import date, datetime, time, tzinfo


DEFAULT_HOTEL_CHECK_IN = time(15, 0)
DEFAULT_HOTEL_CHECK_OUT = time(12, 0)


def resolve_hotel_stay_times(
    check_in_date: date,
    check_out_date: date,
    timezone: tzinfo,
    stated_check_in: time | None = None,
    stated_check_out: time | None = None,
) -> tuple[datetime, datetime]:
    """Return timezone-aware hotel boundaries, applying defaults if omitted."""

    check_in = stated_check_in or DEFAULT_HOTEL_CHECK_IN
    check_out = stated_check_out or DEFAULT_HOTEL_CHECK_OUT
    return (
        datetime.combine(check_in_date, check_in, tzinfo=timezone),
        datetime.combine(check_out_date, check_out, tzinfo=timezone),
    )
