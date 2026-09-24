"""Deterministic, read-only answers from the Jarvis Travels calendar."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import asyncio
import json
import re

from jarvis.sentence_stream import sentence_sink
from zoneinfo import ZoneInfo


class TravelCalendarIntelligence:
    """Answer upcoming-travel questions without exposing the whole calendar to an LLM."""

    _TRAVEL_WORDS = (
        "travel", "travelling", "traveling", "trip", "itinerary", "itineraries",
        "flight", "flights", "hotel", "hotels",
    )
    _DESTINATION_ALIASES = {
        "perth": ("perth", "per"),
        "haugesund": ("haugesund", "hau"),
        "bergen": ("bergen", "bgo"),
        "oslo": ("oslo", "osl"),
        "doha": ("doha", "doh"),
        "dubai": ("dubai", "dxb"),
        "stavanger": ("stavanger", "svg"),
        "copenhagen": ("copenhagen", "cph"),
        "amsterdam": ("amsterdam", "ams"),
        "london": ("london", "lhr", "lgw", "lcy", "stn", "ltn"),
    }
    _AIRPORT_CITIES = {
        "AES": "Ålesund", "AMS": "Amsterdam", "BGO": "Bergen",
        "CPH": "Copenhagen", "DOH": "Doha", "DXB": "Dubai",
        "FRA": "Frankfurt", "HAU": "Haugesund", "HKG": "Hong Kong", "HND": "Tokyo",
        "HOV": "Ørsta-Volda", "LHR": "London", "OSL": "Oslo",
        "MUC": "Munich", "PER": "Perth", "SIN": "Singapore", "SVG": "Stavanger",
    }

    # Presentation only: convert stored instants, never reinterpret wall times.
    _AIRPORT_TIMEZONES = {
        "AES": "Europe/Oslo", "AMS": "Europe/Amsterdam", "BGO": "Europe/Oslo",
        "CPH": "Europe/Copenhagen", "DOH": "Asia/Qatar", "DXB": "Asia/Dubai",
        "FRA": "Europe/Berlin", "HAU": "Europe/Oslo", "HKG": "Asia/Hong_Kong",
        "HND": "Asia/Tokyo", "HOV": "Europe/Oslo", "LHR": "Europe/London",
        "OSL": "Europe/Oslo", "MUC": "Europe/Berlin", "PER": "Australia/Perth",
        "SIN": "Asia/Singapore", "SVG": "Europe/Oslo",
    }

    def __init__(
        self,
        client,
        registry,
        allowed_entities,
        *,
        entity_id: str = "calendar.jarvis_travels",
        lookahead_days: int = 180,
        clock=None,
        reasoning=None,
    ) -> None:
        self._client = client
        self._registry = registry
        self._allowed = frozenset(allowed_entities)
        self._entity_id = entity_id
        self._lookahead_days = max(1, min(int(lookahead_days), 366))
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._reasoning = reasoning
        self._journey_context = {}
        self._pending_journey = {}

    def clear_context(self, conversation_id=None):
        for store in (self._journey_context, self._pending_journey):
            if conversation_id is None:
                store.clear()
            else:
                store.pop(conversation_id, None)

    async def handle(self, text: str, conversation_id: str | None = None):
        normalized = " ".join(text.casefold().strip(" .?!").split())
        now = self._clock()
        self._pending_journey = {key: value for key, value in self._pending_journey.items()
                                 if now - value["updated"] < timedelta(minutes=15)}
        pending = self._pending_journey.get(conversation_id)
        if pending:
            city = self._requested_destination(normalized)
            if city and normalized in city[1]:
                self._pending_journey.pop(conversation_id, None)
                direction = "from" if pending["home"] else "to"
                text = f"When is my travel {direction} {city[0]}?"
                normalized = text.casefold().strip("?")
        self._journey_context = {
            key: value for key, value in self._journey_context.items()
            if now - value["updated"] < timedelta(minutes=15)
        }
        context = self._journey_context.get(conversation_id) if conversation_id else None
        home_question = bool(re.search(r"\b(?:fly|flying|travel|return|returning|arrive|get) (?:back )?home\b", normalized))
        arrival_question = bool(re.search(r"\bwhen (?:do|will) (?:i|we) (?:arrive|get there|land)\b", normalized))
        stop_question = bool(re.search(r"\b(?:stopover|layover|connection time)\b", normalized))
        change_question = bool(re.search(r"\b(?:flight|trip|itinerary|travel)\b.*\bchanged\b|\bhas (?:it|that) changed\b", normalized))
        stop_reply = bool(context and context.get("awaiting_stop") and any(
            normalized in {code.casefold(), self._AIRPORT_CITIES.get(code, code).casefold()}
            for code in context["awaiting_stop"]
        ))
        followup = home_question or arrival_question or stop_question or stop_reply
        if change_question:
            return {"status": "success", "message": "I can read your current itinerary, but I do not have verified itinerary-version history here, so I cannot reliably confirm whether your flight has changed."}
        if followup and not context and self._requested_destination(normalized) is None:
            if conversation_id:
                if len(self._pending_journey) >= 128:
                    self._pending_journey.pop(next(iter(self._pending_journey)))
                self._pending_journey[conversation_id] = {"updated": now, "home": home_question}
            return {"status": "success", "message": "Which journey do you mean? Tell me the departure or destination city."}
        destination = self._requested_destination(normalized)
        from_destination = destination is not None and any(
            re.search(rf"\bfrom\s+{re.escape(alias)}\b", normalized)
            for alias in destination[1]
        )
        direction = "from" if from_destination else "to"
        travel_word = any(re.search(rf"\b{word}\b", normalized) for word in self._TRAVEL_WORDS)
        explicit_travel = travel_word and bool(re.search(
            r"\b(my|our|i|we)\b|\bcoming up\b|\bupcoming\b", normalized
        ))
        personal_destination_timing = destination is not None and bool(
            re.search(r"\b(my|i|we)\b", normalized)
            and re.search(
                r"\b(when|next|going|go|leave|leaving|depart|departure|arrive|arrival|due|scheduled)\b",
                normalized,
            )
        )
        if not explicit_travel and not personal_destination_timing and not followup:
            if conversation_id:
                self.clear_context(conversation_id)
            return None
        if any(word in normalized for word in ("integration", "entity", "dashboard", "card")):
            return None

        entity_id = self._resolve_entity()
        if entity_id is None:
            return {
                "status": "unavailable",
                "message": "The Jarvis Travels calendar is not available in Home Assistant yet.",
            }

        start = self._clock().astimezone(timezone.utc)
        end = start + timedelta(days=self._lookahead_days)
        try:
            response = await self._client.call_service_response(
                "calendar",
                "get_events",
                {
                    "entity_id": entity_id,
                    "start_date_time": start.isoformat(),
                    "end_date_time": end.isoformat(),
                },
            )
            events = tuple(response.get(entity_id, {}).get("events", ()))
        except Exception as error:
            logger = getattr(self._client, "logger", None)
            if logger is not None:
                logger.warning(
                    f"Jarvis Travels calendar read failed safely: {error}"
                )
            return {
                "status": "unavailable",
                "message": "I could not read the Jarvis Travels calendar just now.",
            }

        upcoming = sorted(
            (event for event in events if isinstance(event, dict) and self._active_booking(event)),
            key=lambda event: self._event_time(event, "start") or datetime.max.replace(tzinfo=timezone.utc),
        )
        all_upcoming = list(upcoming)
        if followup and context and (destination is None or stop_question or stop_reply):
            refreshed = [event for event in upcoming if self._context_key(event) in context["keys"]]
            if len(refreshed) != len(context["keys"]):
                self._journey_context.pop(conversation_id, None)
                return {"status": "success", "message": "That journey is no longer fully available in the current calendar. Please ask for the journey again so I can check its latest details."}
            context["updated"] = now
            if stop_question or stop_reply:
                return self._stopover_answer(refreshed, normalized, context)
            if home_question and not context["return_journey"]:
                return {"status": "success", "message": "We were discussing an outbound journey. Which city will you be returning from?"}
            if arrival_question:
                last = refreshed[-1]
                route = self._route(last)
                city = self._AIRPORT_CITIES.get(route[1], route[1]) if route else "your destination"
                return {"status": "success", "message": f"You arrive in {city} on {self._describe_time(last, 'end', route[1] if route else None)}."}
            return {"status": "success", "message": "Your return journey is: " + ". Then ".join(self._describe(event) for event in refreshed) + ".", "preserve_voice_list": True}
        # Known destinations have an exact local airport/city mapping. Do not let
        # probabilistic model selection override those calendar matches.
        local_selection = (
            None if destination is not None and destination[0] in self._DESTINATION_ALIASES
            else await self._select_with_local_qwen(text, upcoming)
        )
        if local_selection is not None:
            upcoming = local_selection
            if not upcoming:
                destination_label = destination[0].title() if destination else "that request"
                return {
                    "status": "success",
                    "message": f"I found no upcoming travel matching {destination_label} in Jarvis Travels.",
                    "source": entity_id,
                    "provider": "ollama",
                }
        if destination is not None:
            label, aliases = destination
            destination_events = [
                event for event in upcoming
                if self._event_matches_direction(event, aliases, from_destination)
            ]
            if not destination_events and local_selection is not None:
                destination_events = list(upcoming)
            upcoming = self._expand_connected_flights(
                all_upcoming, destination_events, forward=from_destination
            )
            if not upcoming:
                return {
                    "status": "success",
                    "message": f"I found no upcoming travel {direction} {label.title()} in Jarvis Travels.",
                    "source": entity_id,
                }
        if not upcoming:
            return {
                "status": "success",
                "message": "You have no travel listed in Jarvis Travels during the next six months.",
                "source": entity_id,
            }

        requested_plural = destination is None and any(
            phrase in normalized
            for phrase in ("what travel", "which travel", "all travel", "trips", "itineraries")
        )
        selected = upcoming[:3] if requested_plural else upcoming[:1]
        if destination is not None:
            selected = upcoming
        if conversation_id and destination is not None and all(self._route(event) for event in selected):
            if len(self._journey_context) >= 128:
                self._journey_context.pop(next(iter(self._journey_context)))
            self._journey_context[conversation_id] = {
                "keys": [self._context_key(event) for event in selected],
                "updated": now, "return_journey": from_destination,
            }
        descriptions = [self._describe(event) for event in selected]
        if destination is not None and len(descriptions) > 1:
            message = (
                f"Your journey {direction} {destination[0].title()} begins with {descriptions[0]}. "
                + " ".join(f"Then {description}." for description in descriptions[1:])
            )
        elif len(descriptions) == 1:
            message = f"Your next travel entry is {descriptions[0]}."
        else:
            message = "Your upcoming travel entries are " + "; then ".join(descriptions) + "."
        result = {"status": "success", "message": message, "source": entity_id}
        if destination is not None and len(descriptions) > 1:
            # A connected journey is a structured spoken list. Do not apply the
            # ordinary concise-answer character limit and drop its final legs.
            result["preserve_voice_list"] = True
        if local_selection is not None:
            result["provider"] = "ollama"
        return result

    @staticmethod
    def _context_key(event):
        # Retain only references, and re-read calendar facts on each follow-up.
        match = re.search(r"Jarvis identity:\s*(.*?)\s*(?:Booking reference:|Hotel reference:|$)", str(event.get("description", "")), re.S)
        return match.group(1).strip() if match else (str(event.get("summary")), str(event.get("start")))

    @classmethod
    def _stopover_answer(cls, events, text, context):
        stops = []
        for left, right in zip(events, events[1:]):
            a, b = cls._route(left), cls._route(right)
            end, start = cls._event_time(left, "end"), cls._event_time(right, "start")
            if a and b and a[1] == b[0] and end and start and start >= end:
                stops.append((a[1], int((start.astimezone(timezone.utc) - end.astimezone(timezone.utc)).total_seconds() // 60)))
        matching = [(code, minutes) for code, minutes in stops if any(
            re.search(rf"\b{re.escape(alias)}\b", text)
            for alias in (code.casefold(), cls._AIRPORT_CITIES.get(code, code).casefold())
        )]
        if matching:
            stops = matching
        if len(stops) > 1:
            context["awaiting_stop"] = [code for code, _ in stops]
            return {"status": "success", "message": "Which stopover do you mean: " + ", ".join(cls._AIRPORT_CITIES.get(code, code) for code, _ in stops) + "?"}
        context.pop("awaiting_stop", None)
        if not stops:
            return {"status": "success", "message": "I cannot find a confirmed connecting stopover in that journey."}
        code, minutes = stops[0]
        return {"status": "success", "message": f"Your stopover in {cls._AIRPORT_CITIES.get(code, code)} is {minutes // 60} hours and {minutes % 60} minutes."}

    @classmethod
    def _expand_connected_flights(cls, events: list[dict], matches: list[dict], *, forward=False) -> list[dict]:
        """Select one journey, walking towards its beginning or its end."""
        if not matches:
            return []
        selected = [min(matches, key=lambda event: cls._event_time(event, "start") or datetime.max.replace(tzinfo=timezone.utc))]
        first = selected[0]
        first_route = cls._route(first)
        first_start = cls._event_time(first, "start")
        if first_route is None or first_start is None:
            return selected

        origin = first_route[1] if forward else first_route[0]
        cursor = cls._event_time(first, "end") if forward else first_start
        if cursor is None:
            return selected
        earlier = sorted(
            (event for event in events if event not in selected),
            key=lambda event: cls._event_time(event, "start") or datetime.max.replace(tzinfo=timezone.utc),
            reverse=not forward,
        )
        while True:
            connection = None
            for event in earlier:
                route = cls._route(event)
                end = cls._event_time(event, "start" if forward else "end")
                if route is None or end is None or route[0 if forward else 1] != origin:
                    continue
                first_ref, candidate_ref = cls._booking_reference(first), cls._booking_reference(event)
                if first_ref and candidate_ref and first_ref != candidate_ref:
                    continue
                gap = (end - cursor) if forward else (cursor - end)
                if timedelta(0) <= gap <= timedelta(hours=36):
                    connection = event
                    break
            if connection is None:
                break
            if forward:
                selected.append(connection)
            else:
                selected.insert(0, connection)
            earlier.remove(connection)
            origin = cls._route(connection)[1 if forward else 0]
            cursor = cls._event_time(connection, "end" if forward else "start")
            if cursor is None:
                break
        return selected

    @staticmethod
    def _booking_reference(event):
        match = re.search(r"(?:Booking|Hotel) reference:\s*([A-Z0-9]+)", str(event.get("description", "")), re.I)
        return match.group(1).upper() if match else None

    @classmethod
    def _active_booking(cls, event):
        summary = str(event.get("summary", ""))
        return not (
            str(event.get("status", "")).casefold() in {"cancelled", "canceled"}
            or re.search(r"\b(?:cancelled|canceled|dummy|jarvis test)\b", summary, re.I)
            or cls._booking_reference(event) in {"JARV01", "JARVH1"}
        )

    @classmethod
    def _event_matches_direction(cls, event, aliases, forward):
        if not forward:
            return cls._event_arrives_at(event, aliases)
        route = cls._route(event)
        return route is not None and route[0].casefold() in aliases

    @staticmethod
    def _route(event: dict) -> tuple[str, str] | None:
        searchable = " ".join(
            str(event.get(field) or "") for field in ("summary", "location")
        ).upper()
        match = re.search(
            r"(?<![A-Z])([A-Z]{3})\s*(?:→|->|–|-)\s*([A-Z]{3})(?![A-Z])",
            searchable,
        )
        return (match.group(1), match.group(2)) if match else None

    @staticmethod
    def _event_time(event: dict, field: str) -> datetime | None:
        try:
            raw = event.get(field)
            if isinstance(raw, dict):
                raw = raw.get("dateTime") or raw.get("date")
            value = datetime.fromisoformat(
                str(raw or "").replace("Z", "+00:00")
            )
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            return None

    async def _select_with_local_qwen(self, text: str, events: list[dict]):
        if self._reasoning is None or not self._needs_interpretation(text):
            return None
        local_reason = getattr(self._reasoning, "reason_local", None)
        if local_reason is None:
            return None
        candidates = [
            {
                "id": index,
                "summary": str(event.get("summary") or "")[:160],
                "start": str(event.get("start") or "")[:80],
                "end": str(event.get("end") or "")[:80],
                "location": str(event.get("location") or "")[:160],
                "description": str(event.get("description") or "")[:120],
            }
            for index, event in enumerate(events[:30])
        ]
        instructions = (
            "You are the private local travel-event selector for Jarvis. Interpret city names, "
            "airport names, IATA codes, routes, hotels, dates and booking references. Select only "
            "events supported by the supplied calendar data. For a destination journey, include "
            "the connected itinerary segments when the data supports the connection. Return JSON "
            "only as {\"matching_event_ids\":[0,1]}. Never answer the question, invent an ID, "
            "or use outside/current information."
        )

        def run():
            # Keep the Node proxy on its proven streaming transport, but never
            # let selector JSON reach TTS before its event IDs are validated.
            token = sentence_sink.set(lambda _sentence: None)
            try:
                return local_reason(
                    instructions=instructions,
                    input_messages=[{
                        "role": "user",
                        "content": json.dumps(
                            {"question": text, "calendar_events": candidates},
                            ensure_ascii=False,
                        ),
                    }],
                    timeout_seconds=30,
                    maximum_output_tokens=60,
                )
            finally:
                sentence_sink.reset(token)

        result = await asyncio.to_thread(run)
        if result.get("status") != "success":
            return None
        try:
            raw = str(result.get("message", "")).strip()
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.IGNORECASE)
            identifiers = json.loads(raw).get("matching_event_ids")
            if not isinstance(identifiers, list):
                return None
            valid = []
            seen = set()
            for identifier in identifiers:
                if isinstance(identifier, int) and 0 <= identifier < len(candidates) and identifier not in seen:
                    valid.append(events[identifier])
                    seen.add(identifier)
            return sorted(valid, key=lambda event: str(event.get("start", "")))
        except (AttributeError, TypeError, ValueError, json.JSONDecodeError):
            return None

    @staticmethod
    def _needs_interpretation(text: str) -> bool:
        normalized = " ".join(text.casefold().strip(" .?!").split())
        return any(marker in normalized for marker in (
            " to ", "when ", "what date", "which date", "flight", "hotel",
            "booking", "reference", "amadeus", "airport", "from ",
        ))

    @classmethod
    def _requested_destination(cls, normalized: str):
        for label, aliases in cls._DESTINATION_ALIASES.items():
            if any(re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", normalized)
                   for alias in aliases):
                return label, aliases
        match = re.search(r"\bto\s+([a-z][a-z-]+)", normalized)
        if match:
            label = match.group(1)
            if label not in {"my", "the", "a", "an"}:
                return label, (label,)
        return None

    @staticmethod
    def _event_mentions(event: dict, aliases) -> bool:
        searchable = " ".join(
            str(event.get(field) or "")
            for field in ("summary", "location", "description")
        ).casefold()
        return any(
            re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", searchable)
            for alias in aliases
        )

    @classmethod
    def _event_arrives_at(cls, event: dict, aliases) -> bool:
        route = cls._route(event)
        airport_aliases = {alias.upper() for alias in aliases if len(alias) == 3}
        if route is not None and airport_aliases:
            return route[1] in airport_aliases
        return cls._event_mentions(event, aliases)

    def _resolve_entity(self) -> str | None:
        entities = tuple(self._registry.all())
        for entity in entities:
            if entity.entity_id == self._entity_id and entity.entity_id in self._allowed:
                return entity.entity_id
        for entity in entities:
            friendly_name = str(entity.attributes.get("friendly_name", "")).casefold()
            if (
                entity.domain == "calendar"
                and entity.entity_id in self._allowed
                and friendly_name == "jarvis travels"
            ):
                return entity.entity_id
        return None

    @classmethod
    def _describe(cls, event: dict) -> str:
        summary = str(event.get("summary") or "a travel booking").strip()
        route = cls._route(event)
        if route is not None:
            origin, destination = route
            human_route = (
                f"{cls._AIRPORT_CITIES.get(origin, origin)} to "
                f"{cls._AIRPORT_CITIES.get(destination, destination)}"
            )
            summary = re.sub(
                r"(?<![A-Z])([A-Z]{3})\s*(?:→|->|–|-)\s*([A-Z]{3})(?![A-Z])",
                human_route,
                summary,
                count=1,
                flags=re.IGNORECASE,
            )
        when = cls._describe_time(event, "start", route[0] if route else None)
        until = cls._describe_time(event, "end", route[1] if route else None)
        return f"{summary}, starting {when}" + (f" and ending {until}" if until else "")

    @classmethod
    def _describe_time(cls, event, field, airport):
        raw = event.get(field)
        if isinstance(raw, dict):
            raw = raw.get("dateTime") or raw.get("date")
        try:
            value = datetime.fromisoformat(str(raw or "").replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return "at an unspecified time" if field == "start" else ""
        suffix = ""
        if value.tzinfo:
            if airport in cls._AIRPORT_TIMEZONES:
                value = value.astimezone(ZoneInfo(cls._AIRPORT_TIMEZONES[airport]))
                suffix = f" {cls._AIRPORT_CITIES.get(airport, airport)} time"
            if not suffix:
                offset = value.strftime("%z")
                suffix = f" UTC{offset[:3]}:{offset[3:]}"
        elif "T" in str(raw):
            suffix = " (time zone unspecified)"
        label = f"{value.strftime('%A')} {value.day} {value.strftime('%B')}"
        if "T" in str(raw):
            label += value.strftime(" at %H:%M")
        return label + suffix
