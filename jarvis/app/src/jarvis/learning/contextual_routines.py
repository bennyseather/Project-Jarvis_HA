"""Bounded, event-derived household routine learning for M47."""
from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from secrets import token_urlsafe


@dataclass(frozen=True, slots=True)
class RoutineLearningPolicy:
    enabled: bool = True
    evidence_threshold: int = 3
    sequence_window_minutes: int = 10
    stale_after_days: int = 45
    maximum_events: int = 500
    maximum_routines: int = 100
    audit_limit: int = 200

    @classmethod
    def from_config(cls, value):
        value = value or {}
        if not isinstance(value, dict):
            raise ValueError("routine_learning must be a mapping")
        enabled = value.get("enabled", True)
        if not isinstance(enabled, bool):
            raise ValueError("routine_learning.enabled must be a boolean")
        bounds = {
            "evidence_threshold": (3, 10, 3),
            "sequence_window_minutes": (2, 60, 10),
            "stale_after_days": (7, 365, 45),
            "maximum_events": (50, 5000, 500),
            "maximum_routines": (10, 500, 100),
            "audit_limit": (10, 1000, 200),
        }
        parsed = {}
        for name, (low, high, default) in bounds.items():
            item = value.get(name, default)
            if isinstance(item, bool) or not isinstance(item, int) or not low <= item <= high:
                raise ValueError(f"routine_learning.{name} must be between {low} and {high}")
            parsed[name] = item
        return cls(enabled=enabled, **parsed)


@dataclass(frozen=True, slots=True)
class RoutinePattern:
    routine_id: str
    signature: str
    description: str
    status: str
    confidence: float
    evidence_days: tuple[str, ...]
    occurrences: int
    first_seen: str
    last_seen: str
    area: str
    day_type: str
    time_period: str
    trigger_entity: str
    trigger_state: str
    action_entity: str
    action_state: str


class SQLiteRoutineLearningStore:
    def __init__(self, database_path: str | Path, policy: RoutineLearningPolicy):
        path = Path(database_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.policy = policy
        self._connection = sqlite3.connect(path)
        with self._connection:
            self._connection.execute(
                "CREATE TABLE IF NOT EXISTS routine_learning_events "
                "(occurred_at TEXT NOT NULL, entity_id TEXT NOT NULL, state TEXT NOT NULL, "
                "area TEXT NOT NULL, day_type TEXT NOT NULL, time_period TEXT NOT NULL)"
            )
            self._connection.execute(
                "CREATE TABLE IF NOT EXISTS contextual_routines "
                "(routine_id TEXT PRIMARY KEY, signature TEXT UNIQUE NOT NULL, payload TEXT NOT NULL)"
            )
            self._connection.execute(
                "CREATE TABLE IF NOT EXISTS contextual_routine_audit "
                "(occurred_at TEXT NOT NULL, event TEXT NOT NULL, routine_id TEXT, payload TEXT NOT NULL)"
            )

    def append_event(self, occurred_at, entity_id, state, area, day_type, time_period):
        with self._connection:
            self._connection.execute(
                "INSERT INTO routine_learning_events VALUES (?,?,?,?,?,?)",
                (occurred_at.isoformat(), entity_id, state, area, day_type, time_period),
            )
            self._connection.execute(
                "DELETE FROM routine_learning_events WHERE rowid NOT IN "
                "(SELECT rowid FROM routine_learning_events ORDER BY occurred_at DESC,rowid DESC LIMIT ?)",
                (self.policy.maximum_events,),
            )

    def recent_events(self, since):
        rows = self._connection.execute(
            "SELECT occurred_at,entity_id,state,area,day_type,time_period "
            "FROM routine_learning_events WHERE occurred_at>=? ORDER BY occurred_at",
            (since.isoformat(),),
        ).fetchall()
        return tuple(rows)

    def get_signature(self, signature):
        row = self._connection.execute(
            "SELECT payload FROM contextual_routines WHERE signature=?", (signature,)
        ).fetchone()
        return None if row is None else self._decode(row[0])

    def get(self, routine_id):
        row = self._connection.execute(
            "SELECT payload FROM contextual_routines WHERE routine_id=?", (routine_id,)
        ).fetchone()
        return None if row is None else self._decode(row[0])

    def save(self, routine):
        payload = json.dumps(asdict(routine), sort_keys=True, separators=(",", ":"))
        with self._connection:
            self._connection.execute(
                "INSERT OR REPLACE INTO contextual_routines VALUES (?,?,?)",
                (routine.routine_id, routine.signature, payload),
            )
        return routine

    def list(self, status=None):
        rows = self._connection.execute(
            "SELECT payload FROM contextual_routines ORDER BY json_extract(payload,'$.last_seen') DESC"
        ).fetchall()
        values = tuple(self._decode(row[0]) for row in rows)
        return values if status is None else tuple(item for item in values if item.status == status)

    def delete(self, routine_id):
        with self._connection:
            return self._connection.execute(
                "DELETE FROM contextual_routines WHERE routine_id=?", (routine_id,)
            ).rowcount > 0

    def audit(self, event, routine_id, payload, now):
        with self._connection:
            self._connection.execute(
                "INSERT INTO contextual_routine_audit VALUES (?,?,?,?)",
                (now.isoformat(), event, routine_id, json.dumps(payload, sort_keys=True)),
            )
            self._connection.execute(
                "DELETE FROM contextual_routine_audit WHERE rowid NOT IN "
                "(SELECT rowid FROM contextual_routine_audit ORDER BY occurred_at DESC,rowid DESC LIMIT ?)",
                (self.policy.audit_limit,),
            )

    def close(self):
        self._connection.close()

    @staticmethod
    def _decode(payload):
        value = json.loads(payload)
        value["evidence_days"] = tuple(value.get("evidence_days", ()))
        return RoutinePattern(**value)


class ContextualRoutineController:
    """Detect repeated safe state-transition sequences across distinct days."""

    _BLOCKED_DOMAINS = {"lock", "alarm_control_panel", "camera", "button", "update"}
    _BLOCKED_TERMS = {"door", "credential", "password", "purchase", "charger", "charging", "oven", "stove"}
    _LEARNABLE_DOMAINS = {"light", "switch", "climate", "cover", "fan", "media_player", "scene", "script", "person"}
    _ACTION_DOMAINS = {"light", "switch", "climate", "cover", "fan", "media_player", "scene", "script"}

    def __init__(self, store, policy, *, blueprint_root=None, clock=None):
        self.store, self.policy = store, policy
        self.blueprint_root = Path(blueprint_root) if blueprint_root else None
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._entity_areas = {}
        self._friendly_names = {}
        self._pending = {}
        self._last_routine_id = {}

    def set_home_references(self, area_members, friendly_names=None):
        for area, entities in (area_members or {}).items():
            for entity_id in entities:
                self._entity_areas[entity_id] = area
        self._friendly_names = dict(friendly_names or {})

    def observe_event(self, event_type, entity_id, occurred_at, state, old_state=None):
        if not self.policy.enabled or event_type != "state_changed" or not state or state == old_state:
            return
        domain = entity_id.split(".", 1)[0]
        lowered = entity_id.casefold()
        if domain not in self._LEARNABLE_DOMAINS or domain in self._BLOCKED_DOMAINS:
            return
        if any(term in lowered for term in self._BLOCKED_TERMS) or "guest" in lowered or "visitor" in lowered:
            return
        local = occurred_at.astimezone()
        day_type = "weekend" if local.weekday() >= 5 else "weekday"
        period = "morning" if local.hour < 12 else "afternoon" if local.hour < 18 else "evening" if local.hour < 22 else "night"
        area = self._entity_areas.get(entity_id, "home")
        window = timedelta(minutes=self.policy.sequence_window_minutes)
        prior = self.store.recent_events(occurred_at - window)
        self.store.append_event(occurred_at, entity_id, state, area, day_type, period)
        for prior_at, prior_entity, prior_state, prior_area, prior_day, prior_period in prior[-12:]:
            if prior_entity == entity_id or prior_day != day_type or prior_period != period:
                continue
            if domain == "person" or prior_entity.startswith("person.") or prior_area == area:
                self._observe_pair(
                    prior_entity, prior_state, entity_id, state,
                    area if area != "home" else prior_area, day_type, period, occurred_at,
                )
                break
        self.refresh_statuses(occurred_at)

    def _observe_pair(self, trigger_entity, trigger_state, action_entity, action_state, area, day_type, period, now):
        if action_entity.split(".", 1)[0] not in self._ACTION_DOMAINS:
            return
        signature = "|".join((day_type, period, area, trigger_entity, trigger_state, action_entity, action_state))
        current = self.store.get_signature(signature)
        day = now.astimezone().date().isoformat()
        if current is None:
            if len(self.store.list()) >= self.policy.maximum_routines:
                return
            description = (
                f"On {day_type} {period}s, {self._name(trigger_entity)} becoming {trigger_state} "
                f"is followed by {self._name(action_entity)} becoming {action_state} in {area}"
            )
            current = RoutinePattern(
                token_urlsafe(12), signature, description, "observed", 0.45, (), 0,
                now.isoformat(), now.isoformat(), area, day_type, period,
                trigger_entity, trigger_state, action_entity, action_state,
            )
        evidence_days = tuple(dict.fromkeys(current.evidence_days + (day,)))[-20:]
        occurrences = current.occurrences + 1
        confidence = min(0.95, 0.35 + 0.2 * len(evidence_days))
        status = current.status
        if status not in {"approved", "declining"} and len(evidence_days) >= self.policy.evidence_threshold:
            status = "suggested"
        updated = self.store.save(replace(
            current, evidence_days=evidence_days, occurrences=occurrences,
            confidence=confidence, status=status, last_seen=now.isoformat(),
        ))
        self.store.audit("observed", updated.routine_id, {"day": day, "confidence": confidence}, now)

    def handle(self, text, conversation_id):
        if not self.policy.enabled:
            return None
        normalized = " ".join(text.casefold().strip(" .?!").split())
        if normalized in {"what routines have you noticed", "show routine insights", "show learned routines", "what routines have you learned"}:
            return self.list_routines()
        if normalized.startswith("why do you think") or normalized.startswith("why did you learn"):
            return self.explain(normalized, conversation_id)
        if normalized.startswith("forget") and "routine" in normalized:
            return self.forget(normalized, conversation_id)
        if "turn that routine into an automation" in normalized or "create an automation from that routine" in normalized:
            return self.propose_automation(conversation_id)
        return None

    def list_routines(self):
        items = self.store.list()
        if not items:
            return {"status": "success", "message": "I have not yet observed a recurring household routine."}
        return {"status": "success", "message": "Routine insights: " + "; ".join(
            f"{item.description} ({len(item.evidence_days)} separate days, {item.status})" for item in items[:8]
        ) + "."}

    def explain(self, text, conversation_id):
        item = self._match(text) or self._last(conversation_id)
        if item is None:
            return {"status": "not_found", "message": "I found no matching routine insight."}
        self._last_routine_id[conversation_id] = item.routine_id
        return {"status": "success", "message": (
            f"I observed that sequence on {len(item.evidence_days)} separate days, "
            f"with {item.confidence:.0%} confidence. It is {item.status} and has not been enabled as an automation."
        )}

    def forget(self, text, conversation_id):
        item = self._match(text) or self._last(conversation_id)
        if item is None:
            return {"status": "not_found", "message": "I found no matching routine insight."}
        self.store.delete(item.routine_id)
        self.store.audit("deleted", item.routine_id, {"signature": item.signature}, self._clock())
        return {"status": "success", "message": f"Forgotten routine insight: {item.description}."}

    def propose_automation(self, conversation_id):
        item = self._last(conversation_id)
        if item is None:
            suggested = self.store.list("suggested")
            item = suggested[0] if suggested else None
        if item is None or item.status not in {"suggested", "approved"}:
            return {"status": "not_found", "message": "There is no eligible routine proposal to automate."}
        token = token_urlsafe(24)
        self._pending[token] = item.routine_id
        return {
            "status": "requires_confirmation", "token": token,
            "summary": f"Create a disabled Home Assistant automation draft for: {item.description}",
            "risk": "routine_automation_creation", "action_payload": {"kind": "routine_automation", "routine_id": item.routine_id},
        }

    def confirm(self, token, payload):
        routine_id = self._pending.pop(token, None)
        if routine_id is None or payload.get("routine_id") != routine_id:
            return {"status": "forbidden", "message": "That routine automation confirmation is invalid or expired."}
        item = self.store.get(routine_id)
        if item is None or self.blueprint_root is None:
            return {"status": "unavailable", "message": "The routine or Home Assistant automation directory is unavailable."}
        folder = self.blueprint_root / "automations.yaml.d"
        folder.mkdir(parents=True, exist_ok=True)
        filename = folder / f"jarvis_routine_{re.sub(r'[^a-z0-9]+', '_', item.routine_id.casefold())}.yaml"
        filename.write_text(self._automation_yaml(item), encoding="utf-8")
        self.store.save(replace(item, status="approved"))
        self.store.audit("automation_draft_created", item.routine_id, {"path": str(filename)}, self._clock())
        return {"status": "success", "message": f"A disabled Home Assistant automation draft was created for {item.description}. Review it before enabling it."}

    def insights(self):
        self.refresh_statuses()
        items = self.store.list()
        return {
            "state": len(items),
            "observed": sum(item.status == "observed" for item in items),
            "suggested": sum(item.status == "suggested" for item in items),
            "approved": sum(item.status == "approved" for item in items),
            "declining": sum(item.status == "declining" for item in items),
            "routines": [asdict(item) for item in items[:20]],
        }

    def refresh_statuses(self, now=None):
        now = now or self._clock()
        cutoff = now - timedelta(days=self.policy.stale_after_days)
        for item in self.store.list():
            if item.status in {"suggested", "approved"} and datetime.fromisoformat(item.last_seen) < cutoff:
                self.store.save(replace(item, status="declining", confidence=max(0.25, item.confidence - 0.2)))

    def _match(self, text):
        words = set(re.findall(r"[a-z0-9]+", text)) - {"why", "do", "you", "think", "forget", "routine", "the"}
        ranked = sorted(self.store.list(), key=lambda item: len(words & set(re.findall(r"[a-z0-9]+", item.description.casefold()))), reverse=True)
        return ranked[0] if ranked and words & set(re.findall(r"[a-z0-9]+", ranked[0].description.casefold())) else None

    def _last(self, conversation_id):
        routine_id = self._last_routine_id.get(conversation_id)
        return self.store.get(routine_id) if routine_id else None

    def _name(self, entity_id):
        return self._friendly_names.get(entity_id, entity_id.split(".", 1)[-1].replace("_", " "))

    @staticmethod
    def _automation_yaml(item):
        service = "turn_on" if item.action_state in {"on", "open", "playing", "home"} else "turn_off"
        return (
            f"# Generated by Project Jarvis M47. Review before enabling.\n"
            f"alias: Jarvis learned routine - {item.area}\n"
            f"description: \"{item.description.replace(chr(34), chr(39))}\"\n"
            f"initial_state: false\nmode: single\n"
            f"trigger:\n  - platform: state\n    entity_id: {item.trigger_entity}\n    to: \"{item.trigger_state}\"\n"
            f"condition:\n  - condition: time\n    after: \"{ {'morning':'05:00:00','afternoon':'12:00:00','evening':'18:00:00','night':'22:00:00'}[item.time_period] }\"\n"
            f"action:\n  - service: homeassistant.{service}\n    target:\n      entity_id: {item.action_entity}\n"
        )
