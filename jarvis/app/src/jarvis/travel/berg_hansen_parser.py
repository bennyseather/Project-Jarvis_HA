"""Strict parser for Berg-Hansen HTML itinerary relay messages."""

from __future__ import annotations

import re
from datetime import date, time
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

from jarvis.travel.airport_timezones import resolve_flight_times
from jarvis.travel.models import TravelSegment, TravelStatus
from jarvis.travel.policy import resolve_hotel_stay_times


_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
_STAMP = re.compile(
    r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+"
    r"(?P<day>\d{1,2})\.?\s+(?P<month>[A-Za-z]{3})\s+(?P<year>\d{4}),\s+"
    r"at\s+(?P<hour>\d{1,2}):(?P<minute>\d{2})\s+[^\n]*?\((?P<airport>[A-Z]{3})\)",
    re.IGNORECASE,
)
_PERIOD_DATE = re.compile(
    r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+"
    r"(?P<day>\d{1,2})\s+(?P<month>[A-Za-z]{3})\s+(?P<year>\d{4})",
    re.IGNORECASE,
)


class ItineraryParseError(ValueError):
    """Raised when relay content cannot be normalized without guessing."""


class _BlockTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.paragraphs: list[str] = []
        self.paragraph_links: list[tuple[str, ...]] = []
        self.headings: list[str] = []
        self._tag: str | None = None
        self._parts: list[str] = []
        self._links: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"p", "h2"}:
            self._tag = tag
            self._parts = []
            self._links = []
        elif tag == "br" and self._tag:
            self._parts.append("\n")
        elif tag == "a" and self._tag == "p":
            attributes = dict(attrs)
            source = attributes.get("originalsrc") or attributes.get("href")
            if source:
                self._links.append(source)

    def handle_data(self, data: str) -> None:
        if self._tag:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != self._tag:
            return
        text = "".join(self._parts)
        text = "\n".join(
            re.sub(r"\s+", " ", line).strip()
            for line in text.splitlines()
            if line.strip()
        )
        if tag == "h2":
            self.headings.append(text)
        else:
            self.paragraphs.append(text)
            self.paragraph_links.append(tuple(self._links))
        self._tag = None
        self._parts = []


def _date_time(match: re.Match[str]) -> tuple[date, time, str]:
    try:
        month = _MONTHS[match.group("month").casefold()]
    except KeyError as exc:
        raise ItineraryParseError("unsupported itinerary month") from exc
    return (
        date(int(match.group("year")), month, int(match.group("day"))),
        time(int(match.group("hour")), int(match.group("minute"))),
        match.group("airport").upper(),
    )


def _period_date(match: re.Match[str]) -> date:
    try:
        month = _MONTHS[match.group("month").casefold()]
    except KeyError as exc:
        raise ItineraryParseError("unsupported hotel month") from exc
    return date(int(match.group("year")), month, int(match.group("day")))


def parse_berg_hansen_html(html: str) -> list[TravelSegment]:
    blocks = _BlockTextParser()
    blocks.feed(html)
    passenger = next((value for value in blocks.headings if value.strip()), "")
    if not passenger:
        raise ItineraryParseError("missing passenger heading")

    segments: list[TravelSegment] = []
    for paragraph, links in zip(blocks.paragraphs, blocks.paragraph_links):
        if paragraph.startswith("Air:"):
            segments.append(_parse_flight(paragraph, links, passenger))
        elif paragraph.startswith("Hotel:"):
            segments.append(_parse_hotel(paragraph, links, passenger))
    if not segments:
        raise ItineraryParseError("no supported itinerary segments found")
    return segments


def _amadeus_segment_reference(links: tuple[str, ...]) -> str:
    for link in links:
        query = parse_qs(urlparse(link).query)
        pnr = query.get("GdsPNR", [""])[0].strip()
        reservation_type = query.get("ResType", [""])[0].strip()
        reservation_number = query.get("ResNo", [""])[0].strip()
        if pnr and reservation_type and reservation_number:
            return f"{reservation_type}:{pnr}:{reservation_number}"
    raise ItineraryParseError("missing stable Amadeus segment identity")


def _parse_flight(
    text: str, links: tuple[str, ...], passenger: str
) -> TravelSegment:
    header = re.search(r"^Air:\s+(?P<flight>[A-Z0-9]{2}\d{2,4})\s+.*?\s+-\s+Calendar", text)
    reference = re.search(r"Reference:\s*(?P<value>[A-Z0-9]+)", text)
    stamps = list(_STAMP.finditer(text))
    status = re.search(r"Status:\s*(?P<value>[^\n]+)", text)
    if not header or not reference or len(stamps) != 2 or not status:
        raise ItineraryParseError("incomplete flight block")

    departure_date, departure_time, origin = _date_time(stamps[0])
    arrival_date, arrival_time, destination = _date_time(stamps[1])
    starts_at, ends_at = resolve_flight_times(
        origin,
        departure_date,
        departure_time,
        destination,
        arrival_date,
        arrival_time,
    )
    flight = header.group("flight").upper()
    return TravelSegment(
        booking_reference=reference.group("value"),
        passenger_name=passenger,
        segment_reference=_amadeus_segment_reference(links),
        segment_type="flight",
        origin=origin,
        destination=destination,
        starts_at=starts_at,
        ends_at=ends_at,
        title=f"{flight} · {origin} → {destination}",
        location=f"{origin} → {destination}",
        details=f"Booking reference: {reference.group('value')}\nFlight: {flight}",
        status=(
            TravelStatus.CONFIRMED
            if status.group("value").strip().casefold().startswith("confirmed")
            else TravelStatus.CANCELLED
        ),
    )


def _parse_hotel(
    text: str, links: tuple[str, ...], passenger: str
) -> TravelSegment:
    header = re.search(r"^Hotel:\s+(?P<name>.*?)\s+-\s+Map\s+-\s+Calendar", text)
    reference = re.search(r"Reference:\s*(?P<value>[A-Z0-9]+)", text)
    address = re.search(r"Address:\s*(?P<value>[^\n]+)", text)
    period = re.search(r"Period:\s*(?P<value>[^\n]+)", text)
    status = re.search(r"Status:\s*(?P<value>[^\n]+)", text)
    if not header or not reference or not address or not period or not status:
        raise ItineraryParseError("incomplete hotel block")
    dates = list(_PERIOD_DATE.finditer(period.group("value")))
    if len(dates) != 2:
        raise ItineraryParseError("hotel period is ambiguous")
    hotel_address = address.group("value")
    if not re.search(r"\bNORWAY\b", hotel_address, re.IGNORECASE):
        raise ItineraryParseError("hotel timezone requires review")
    check_in_date, check_out_date = map(_period_date, dates)
    starts_at, ends_at = resolve_hotel_stay_times(
        check_in_date,
        check_out_date,
        ZoneInfo("Europe/Oslo"),
    )
    name = header.group("name").strip().title()
    return TravelSegment(
        booking_reference=reference.group("value"),
        passenger_name=passenger,
        segment_reference=_amadeus_segment_reference(links),
        segment_type="hotel",
        origin=hotel_address,
        destination=hotel_address,
        starts_at=starts_at,
        ends_at=ends_at,
        title=name,
        location=hotel_address,
        details=f"Hotel reference: {reference.group('value')}",
        status=(
            TravelStatus.CONFIRMED
            if status.group("value").strip().casefold().startswith("confirmed")
            else TravelStatus.CANCELLED
        ),
    )
