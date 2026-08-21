"""Extensible, local-first capability selection for Jarvis requests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, date
import re
from zoneinfo import ZoneInfo


@dataclass(frozen=True, slots=True)
class RequestEnvelope:
    text: str
    conversation_id: str = "local-default"
    source_id: str = ""
    room_id: str = ""
    voice_mode: bool = False
    received_at: float = 0.0


@dataclass(frozen=True, slots=True)
class CapabilityDecision:
    capability: str
    reason: str
    deterministic: bool = False
    time_sensitive: bool = False


class LocalCapabilityRegistry:
    """Select a broad capability from intent properties, not topic aliases."""

    _ACTION = re.compile(r"\b(turn|switch|set|dim|open|close|lock|unlock|start|stop|pause|resume)\b", re.I)
    _HOME = re.compile(
        r"\b(lights?|lamps?|blinds?|covers?|thermostats?|temperatures?|humidity|sensors?|doors?|windows?|"
        r"scenes?|automations?|vacuums?|mowers?|washing machines?|home assistant)\b", re.I
    )
    _HOME_STATE = re.compile(
        r"\b(lights?|lamps?|blinds?|covers?|thermostats?|temperatures?|humidity|sensors?|doors?|windows?|"
        r"scenes?|automations?|vacuums?|mowers?|washing machines?)\b", re.I
    )
    _CURRENT = re.compile(
        r"\b(latest|newest|current(?:ly)?|today|tonight|recent(?:ly)?|released?|version|"
        r"price|cost|schedule|score|standings|office.?holder|president|prime minister|ceo|"
        r"weather|forecast|news|exchange rate|stock price)\b", re.I
    )
    _LOCAL_FACT = re.compile(
        r"\b(what|which|tell|how many|calculate|compute|convert)\b.*\b(day|date|time|days? until|"
        r"days? to|weeks? until|months? until|christmas|new year)\b", re.I
    )
    _PERSONAL = re.compile(
        r"\b(remember|forget|learned|preference|routine|my calendar|my appointment|my password|my pin)\b", re.I
    )

    def decide(self, text: str) -> CapabilityDecision:
        value = " ".join(str(text).split())
        if self._ACTION.search(value) and self._HOME.search(value):
            return CapabilityDecision("home_assistant", "explicit_home_action", True)
        if self._LOCAL_FACT.search(value):
            return CapabilityDecision("local_facts", "device_clock_or_calculation", True)
        if self._CURRENT.search(value) and not self._HOME_STATE.search(value):
            return CapabilityDecision("current_information", "time_sensitive_fact", False, True)
        if self._HOME.search(value):
            return CapabilityDecision("home_assistant", "home_state_or_capability", True)
        if self._PERSONAL.search(value):
            return CapabilityDecision("memory_knowledge", "personal_context", True)
        return CapabilityDecision("general_reasoning", "local_model_reasoning")


class LocalFacts:
    """Fast deterministic clock and calendar arithmetic without model/search."""

    _UNTIL = re.compile(r"\b(?:how many\s+)?days?\s+(?:until|to|before)\s+(.+?)[?.!]*$", re.I)
    _MONTHS = {
        name.casefold(): number for number, name in enumerate(
            ("", "January", "February", "March", "April", "May", "June", "July",
             "August", "September", "October", "November", "December")
        ) if name
    }

    def __init__(self, time_zone="Europe/Oslo", clock=None):
        self.time_zone = time_zone
        self.clock = clock or (lambda: datetime.now(ZoneInfo(time_zone)))

    def handle(self, text: str):
        value = " ".join(str(text).casefold().strip().split())
        now = self.clock()
        if now.tzinfo is None:
            now = now.replace(tzinfo=ZoneInfo(self.time_zone))
        match = self._UNTIL.search(value)
        if match:
            target = self._target(match.group(1), now.date())
            if target is not None:
                days = (target - now.date()).days
                return {"status": "success", "message": f"There are {days} days until {target.day} {target.strftime('%B %Y')}.", "provider": "local_facts"}
        return None

    def _target(self, phrase: str, today: date):
        phrase = phrase.strip(" .?!")
        if phrase in {"christmas", "christmas day"}:
            target = date(today.year, 12, 25)
            return target if target >= today else date(today.year + 1, 12, 25)
        if phrase in {"new year", "new year's day", "new years day"}:
            target = date(today.year + 1, 1, 1)
            return target
        match = re.search(r"\b(\d{1,2})\s+([a-z]+)(?:\s+(\d{4}))?\b", phrase)
        if not match or match.group(2) not in self._MONTHS:
            return None
        year = int(match.group(3) or today.year)
        try:
            target = date(year, self._MONTHS[match.group(2)], int(match.group(1)))
        except ValueError:
            return None
        return target if target >= today or match.group(3) else date(year + 1, target.month, target.day)
