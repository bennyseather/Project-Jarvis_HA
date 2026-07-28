"""Deterministic policy for proactive suggestions and delivery."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone

from jarvis.models.proactive import ProactiveCandidate, ProactiveSuggestion


def _clock_time(value: str, name: str) -> time:
    if not isinstance(value, str):
        raise ValueError(f"proactive.{name} must use HH:MM")
    try:
        return time.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"proactive.{name} must use HH:MM") from error


@dataclass(frozen=True, slots=True)
class ProactiveAssistancePolicy:
    enabled: bool = True
    minimum_confidence: float = 0.8
    maximum_pending: int = 10
    expiry_hours: int = 24
    cooldown_minutes: int = 60
    snooze_minutes: int = 120
    quiet_start: time = time(22, 0)
    quiet_end: time = time(7, 0)
    notification_enabled: bool = True
    voice_enabled: bool = False
    scan_interval_seconds: int = 300
    low_battery_threshold: int = 20
    routine_repeat_threshold: int = 3

    @classmethod
    def from_config(cls, value: dict | None) -> "ProactiveAssistancePolicy":
        config = {} if value is None else value
        if not isinstance(config, dict):
            raise ValueError("proactive must be a mapping")
        boolean_names = ("enabled", "notification_enabled", "voice_enabled")
        for name in boolean_names:
            if name in config and not isinstance(config[name], bool):
                raise ValueError(f"proactive.{name} must be a boolean")
        numeric_ranges = {
            "minimum_confidence": (0.0, 1.0),
            "maximum_pending": (1, 50),
            "expiry_hours": (1, 168),
            "cooldown_minutes": (1, 1440),
            "snooze_minutes": (1, 10080),
            "scan_interval_seconds": (30, 3600),
            "low_battery_threshold": (1, 50),
            "routine_repeat_threshold": (3, 20),
        }
        for name, (minimum, maximum) in numeric_ranges.items():
            if name not in config:
                continue
            item = config[name]
            if name == "minimum_confidence":
                valid = isinstance(item, (int, float)) and not isinstance(item, bool)
            else:
                valid = isinstance(item, int) and not isinstance(item, bool)
            if not valid or not minimum <= item <= maximum:
                raise ValueError(
                    f"proactive.{name} must be between {minimum} and {maximum}"
                )
        return cls(
            enabled=config.get("enabled", True),
            minimum_confidence=float(config.get("minimum_confidence", 0.8)),
            maximum_pending=config.get("maximum_pending", 10),
            expiry_hours=config.get("expiry_hours", 24),
            cooldown_minutes=config.get("cooldown_minutes", 60),
            snooze_minutes=config.get("snooze_minutes", 120),
            quiet_start=_clock_time(config.get("quiet_start", "22:00"), "quiet_start"),
            quiet_end=_clock_time(config.get("quiet_end", "07:00"), "quiet_end"),
            notification_enabled=config.get("notification_enabled", True),
            voice_enabled=config.get("voice_enabled", False),
            scan_interval_seconds=config.get("scan_interval_seconds", 300),
            low_battery_threshold=config.get("low_battery_threshold", 20),
            routine_repeat_threshold=config.get("routine_repeat_threshold", 3),
        )

    def permits_candidate(
        self, candidate: ProactiveCandidate, *, suppressed: bool
    ) -> bool:
        return bool(
            self.enabled
            and not suppressed
            and not candidate.sensitive
            and self.minimum_confidence <= candidate.confidence <= 1.0
            and candidate.subject.strip()
            and candidate.message.strip()
            and candidate.reason.strip()
        )

    def is_quiet(self, now: datetime | None = None) -> bool:
        local = (now or datetime.now(timezone.utc)).astimezone().timetz().replace(
            tzinfo=None
        )
        if self.quiet_start == self.quiet_end:
            return False
        if self.quiet_start < self.quiet_end:
            return self.quiet_start <= local < self.quiet_end
        return local >= self.quiet_start or local < self.quiet_end

    def delivery_due(
        self, suggestion: ProactiveSuggestion, channel: str, now: datetime
    ) -> bool:
        if channel in suggestion.delivered_channels or self.is_quiet(now):
            return False
        if suggestion.snoozed_until is not None and now < suggestion.snoozed_until:
            return False
        return True
