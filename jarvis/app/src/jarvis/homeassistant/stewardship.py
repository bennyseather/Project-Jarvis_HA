"""Durable, policy-controlled whole-home stewardship modes."""
from __future__ import annotations

import json
import re
import sqlite3
import calendar
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from secrets import token_urlsafe

from jarvis.models.home_assistant_gateway import HomeAssistantActionProposal


@dataclass(frozen=True, slots=True)
class StewardshipPolicy:
    enabled: bool = True
    require_confirmation: bool = False
    reconciliation_seconds: int = 300
    maximum_targets: int = 100
    confirmation_ttl_seconds: int = 300
    manual_override_minutes: int = 30
    audit_limit: int = 100

    @classmethod
    def from_config(cls, value):
        value = {} if value is None else value
        if not isinstance(value, dict):
            raise ValueError("stewardship must be a mapping")
        enabled = value.get("enabled", True)
        require_confirmation = value.get("require_confirmation", False)
        if not isinstance(enabled, bool):
            raise ValueError("stewardship.enabled must be a boolean")
        if not isinstance(require_confirmation, bool):
            raise ValueError("stewardship.require_confirmation must be a boolean")
        bounds = {
            "reconciliation_seconds": (30, 3600, 300),
            "maximum_targets": (1, 200, 100),
            "confirmation_ttl_seconds": (30, 600, 300),
            "manual_override_minutes": (0, 1440, 30),
            "audit_limit": (10, 500, 100),
        }
        values = {}
        for name, (low, high, default) in bounds.items():
            item = value.get(name, default)
            if not isinstance(item, int) or isinstance(item, bool) or not low <= item <= high:
                raise ValueError(f"stewardship.{name} must be between {low} and {high}")
            values[name] = item
        return cls(enabled=enabled, require_confirmation=require_confirmation, **values)


@dataclass(frozen=True, slots=True)
class StewardshipMode:
    mode_id: str
    name: str
    activated_at: str
    expires_at: str | None
    lights_off: bool
    climate_temperature: float | None
    excluded_entities: tuple[str, ...]
    restore_states: tuple[dict[str, object], ...] = ()
    monitor_exceptions: bool = True
    presence_simulation: bool = False


class SQLiteStewardshipStore:
    def __init__(self, database_path: str | Path, *, audit_limit=100):
        path = Path(database_path); path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(path)
        self.audit_limit = audit_limit
        with self._connection:
            self._connection.execute("CREATE TABLE IF NOT EXISTS stewardship_state (slot INTEGER PRIMARY KEY CHECK(slot=1), payload TEXT NOT NULL)")
            self._connection.execute("CREATE TABLE IF NOT EXISTS stewardship_audit (occurred_at TEXT NOT NULL, event TEXT NOT NULL, payload TEXT NOT NULL)")
            self._connection.execute("CREATE TABLE IF NOT EXISTS stewardship_alerts (fingerprint TEXT PRIMARY KEY, occurred_at TEXT NOT NULL)")

    def active(self):
        row = self._connection.execute("SELECT payload FROM stewardship_state WHERE slot=1").fetchone()
        if row is None: return None
        value = json.loads(row[0]); value["excluded_entities"] = tuple(value.get("excluded_entities", ())); value["restore_states"] = tuple(value.get("restore_states", ()))
        return StewardshipMode(**value)

    def save(self, mode):
        payload = json.dumps(asdict(mode), sort_keys=True, separators=(",", ":"))
        with self._connection:
            self._connection.execute("INSERT OR REPLACE INTO stewardship_state VALUES (1, ?)", (payload,))

    def clear(self):
        with self._connection: self._connection.execute("DELETE FROM stewardship_state")

    def audit(self, event, payload, occurred_at):
        with self._connection:
            self._connection.execute("INSERT INTO stewardship_audit VALUES (?, ?, ?)", (occurred_at.isoformat(), event, json.dumps(payload, sort_keys=True)))
            self._connection.execute("DELETE FROM stewardship_audit WHERE rowid NOT IN (SELECT rowid FROM stewardship_audit ORDER BY occurred_at DESC, rowid DESC LIMIT ?)", (self.audit_limit,))

    def recent(self, limit=10):
        return tuple(self._connection.execute("SELECT occurred_at,event,payload FROM stewardship_audit ORDER BY occurred_at DESC,rowid DESC LIMIT ?", (min(max(limit, 1), 50),)))

    def claim_alert(self, fingerprint, occurred_at):
        with self._connection:
            inserted = self._connection.execute(
                "INSERT OR IGNORE INTO stewardship_alerts VALUES (?,?)",
                (fingerprint, occurred_at.isoformat()),
            ).rowcount
        return bool(inserted)

    def clear_alerts(self):
        with self._connection: self._connection.execute("DELETE FROM stewardship_alerts")

    def close(self): self._connection.close()


class StewardshipController:
    """Preview, activate, reconcile and cancel bounded home modes."""
    _MODES = {"home", "away", "vacation", "sleep", "custom"}

    def __init__(self, client, assembler, gateway, store, policy, *, clock=None):
        self._client, self._assembler, self._gateway = client, assembler, gateway
        self.store, self.policy = store, policy
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._pending = {}
        self._manual = {}
        self._expected = {}

    async def handle(self, text, conversation_id):
        if not self.policy.enabled: return None
        normalized = " ".join(text.casefold().strip(" .?!").split())
        if normalized in {"show stewardship mode", "stewardship status", "show house mode", "what mode is the house in"}:
            return self.status()
        if normalized in {"show stewardship audit", "show stewardship history", "what has stewardship done"}:
            return self.audit_status()
        if self._is_morning_return(normalized):
            active = self.store.active()
            if active is not None and active.name == "sleep":
                return await self._end_sleep_and_start_morning(active)
            return None
        if self._is_return_home(normalized):
            return await self.cancel()
        if not self._is_mode_request(normalized): return None
        mode = self._parse(normalized)
        try: snapshot = self._assembler.assemble(await self._client.get_states(), captured_at=self._clock())
        except Exception: return {"status": "unavailable", "message": "Home Assistant data is unavailable."}
        mode = replace(mode, restore_states=self._capture_restore_states(snapshot))
        plan = self._plan(mode, snapshot)
        if isinstance(plan, dict): return plan
        if not self.policy.require_confirmation:
            return await self._activate(mode)
        token = token_urlsafe(24)
        self._pending[token] = (self._clock() + timedelta(seconds=self.policy.confirmation_ttl_seconds), mode)
        return {"status": "requires_confirmation", "token": token, "summary": plan, "risk": "stewardship_confirmation_required", "action_payload": {"kind": "stewardship_mode", "conversation_id": conversation_id}}

    async def confirm(self, token, payload):
        pending = self._pending.pop(token, None)
        if pending is None or pending[0] < self._clock() or payload.get("kind") != "stewardship_mode":
            return {"status": "forbidden", "message": "Stewardship confirmation is invalid or expired."}
        return await self._activate(pending[1])

    async def _activate(self, mode):
        self.store.save(mode)
        self.store.clear_alerts()
        self.store.audit("activated", {"mode": mode.name, "mode_id": mode.mode_id}, self._clock())
        result = await self.reconcile()
        return {"status": result["status"], "message": f"{mode.name.title()} stewardship mode is active. {result['message']}"}

    def status(self):
        mode = self.store.active()
        if mode is None: return {"status": "success", "message": "No stewardship mode is active."}
        expiry = "until cancelled" if mode.expires_at is None else f"until {mode.expires_at}"
        temperature = "no climate target" if mode.climate_temperature is None else f"climate at {mode.climate_temperature:.1f} degrees"
        simulation = "presence simulation enabled" if mode.presence_simulation else "presence simulation disabled"
        return {"status": "success", "message": f"{mode.name.title()} mode is active {expiry}: lights {'off' if mode.lights_off else 'unchanged'}, {temperature}, {simulation}, {len(mode.excluded_entities)} exclusions."}

    def audit_status(self):
        events = self.store.recent(10)
        if not events: return {"status": "success", "message": "The stewardship audit is empty."}
        return {"status": "success", "message": "Recent stewardship activity: " + "; ".join(f"{event} at {occurred_at}" for occurred_at, event, _payload in events) + "."}

    async def cancel(self):
        mode = self.store.active()
        if mode is None: return {"status": "success", "message": "No stewardship mode is active."}
        restoration = await self._restore(mode)
        self.store.clear(); self.store.clear_alerts(); self.store.audit("cancelled", {"mode": mode.name, "mode_id": mode.mode_id, "restored": restoration[0], "failed": restoration[1]}, self._clock())
        return {"status": "success" if not restoration[1] else "unavailable", "message": f"{mode.name.title()} stewardship mode has ended. Restored {restoration[0]} prior Home Assistant states; {restoration[1]} were unavailable."}

    async def _end_sleep_and_start_morning(self, mode):
        restored, failed = await self._restore(mode)
        self.store.clear(); self.store.clear_alerts()
        try:
            snapshot = self._assembler.assemble(await self._client.get_states(), captured_at=self._clock())
        except Exception:
            self.store.audit("morning_started", {"mode": mode.name, "restored": restored, "failed": failed, "lights_on": 0, "snapshot_unavailable": True}, self._clock())
            return {"status": "unavailable", "message": f"Good morning. Sleep stewardship has ended and {restored} prior states were restored, but Home Assistant state was unavailable for the interior lights."}
        targets = tuple(
            entity.entity_id for entity in snapshot.entities
            if entity.domain == "light" and entity.action_allowed
            and entity.state not in {"on", "unavailable", "unknown"}
            and self._is_interior_light(entity)
        )
        lights_on = 0
        for chunk in self._chunks(targets):
            proposal = HomeAssistantActionProposal("light", "turn_on", chunk, {}, "Stewardship: morning interior lights")
            if self._gateway.request(proposal).get("status") != "immediate_action":
                failed += len(chunk)
                continue
            result = await self._gateway.execute_immediate(proposal)
            lights_on += len(result.get("succeeded", ())); failed += len(result.get("failed", ()))
        self.store.audit("morning_started", {"mode": mode.name, "restored": restored, "failed": failed, "lights_on": lights_on}, self._clock())
        return {
            "status": "success" if not failed else "unavailable",
            "message": f"Good morning. Sleep stewardship has ended, {restored} prior states were restored, and {lights_on} interior lights were switched on; {failed} actions were unavailable.",
        }

    async def reconcile(self):
        mode = self.store.active()
        if mode is None: return {"status": "success", "message": "No reconciliation was required."}
        if mode.expires_at and datetime.fromisoformat(mode.expires_at) <= self._clock():
            restored, failed = await self._restore(mode)
            self.store.clear(); self.store.clear_alerts(); self.store.audit("expired", {"mode": mode.name, "restored": restored, "failed": failed}, self._clock())
            return {"status": "success" if not failed else "unavailable", "message": f"{mode.name.title()} mode expired safely. Restored {restored} prior states; {failed} were unavailable."}
        try: snapshot = self._assembler.assemble(await self._client.get_states(), captured_at=self._clock())
        except Exception:
            self.store.audit("reconcile_unavailable", {"mode": mode.name}, self._clock())
            return {"status": "unavailable", "message": "Home Assistant state was unavailable; no action was taken."}
        proposals = self._proposals(mode, snapshot)
        succeeded = failed = skipped = 0
        for proposal in proposals:
            decision = self._gateway.request(proposal)
            if decision.get("status") != "immediate_action": skipped += len(proposal.entity_ids); continue
            result = await self._gateway.execute_immediate(proposal)
            succeeded += len(result.get("succeeded", ())); failed += len(result.get("failed", ()))
            expected = "off" if proposal.service == "turn_off" else mode.climate_temperature
            for entity_id in result.get("succeeded", ()):
                self._expected[entity_id] = expected
        exceptions = self._exceptions(mode, snapshot)
        notified = await self._notify_exceptions(mode, exceptions)
        self.store.audit("reconciled", {"mode": mode.name, "succeeded": succeeded, "failed": failed, "skipped": skipped, "exceptions": len(exceptions), "notified": notified}, self._clock())
        status = "success" if not failed else "unavailable"
        exception_text = "" if not exceptions else f" {len(exceptions)} exception{'s' if len(exceptions) != 1 else ''} detected; {notified} new alert{'s' if notified != 1 else ''} issued."
        return {"status": status, "message": f"Reconciliation complete: {succeeded} corrected, {skipped} policy-skipped, {failed} unavailable.{exception_text}"}

    def _plan(self, mode, snapshot):
        proposals = self._proposals(mode, snapshot)
        count = sum(len(item.entity_ids) for item in proposals)
        if count > self.policy.maximum_targets:
            return {"status": "clarification_required", "message": f"That mode affects {count} entities; narrow it to {self.policy.maximum_targets} or fewer."}
        details = []
        if mode.lights_off: details.append("keep authorized lights off")
        if mode.climate_temperature is not None: details.append(f"keep authorized climate entities at {mode.climate_temperature:.1f} degrees")
        if mode.presence_simulation: details.append("simulate evening presence with at most two authorized lights")
        if mode.monitor_exceptions: details.append("monitor safety, perimeter and availability exceptions")
        details.append(f"restore up to {len(mode.restore_states)} prior states when the mode ends")
        details.append(f"exclude {len(mode.excluded_entities)} entities")
        details.append("leave locks, alarms and cameras unchanged")
        return f"Activate {mode.name} mode: " + "; ".join(details) + f". Current correction targets: {count}."

    def _proposals(self, mode, snapshot):
        excluded = set(mode.excluded_entities); entities = snapshot.entities
        proposals = []
        now = self._clock()
        for entity in entities:
            expected = self._expected.get(entity.entity_id)
            changed = (
                expected == "off" and entity.state != "off"
                or isinstance(expected, float) and self._temperature_differs(entity.attributes, expected)
            )
            if expected is not None and changed:
                self._manual[entity.entity_id] = now + timedelta(minutes=self.policy.manual_override_minutes)
                self._expected.pop(entity.entity_id, None)
        self._manual = {entity_id: until for entity_id, until in self._manual.items() if until > now}
        if mode.lights_off:
            targets = tuple(e.entity_id for e in entities if e.domain == "light" and e.action_allowed and e.entity_id not in excluded and e.entity_id not in self._manual and e.state not in {"off", "unavailable", "unknown"})
            for chunk in self._chunks(targets): proposals.append(HomeAssistantActionProposal("light", "turn_off", chunk, {}, "Stewardship: switch off lights"))
        if mode.climate_temperature is not None:
            targets = tuple(e.entity_id for e in entities if e.domain == "climate" and e.action_allowed and e.entity_id not in excluded and e.entity_id not in self._manual and e.state not in {"off", "unavailable", "unknown"} and self._temperature_differs(e.attributes, mode.climate_temperature))
            for chunk in self._chunks(targets): proposals.append(HomeAssistantActionProposal("climate", "set_temperature", chunk, {"temperature": mode.climate_temperature}, "Stewardship: set climate temperature"))
        if mode.presence_simulation:
            evening = 18 <= now.astimezone().hour < 23
            candidates = tuple(e.entity_id for e in entities if e.domain == "light" and e.action_allowed and e.entity_id not in excluded and e.entity_id not in self._manual and e.state not in {"unavailable", "unknown"})[:2]
            targets = tuple(entity_id for entity_id in candidates if (snapshot.entity_map()[entity_id].state == "on") != evening)
            if targets: proposals.append(HomeAssistantActionProposal("light", "turn_on" if evening else "turn_off", targets, {}, "Stewardship: bounded presence simulation"))
        return proposals

    def _parse(self, text):
        name = self._infer_mode(text)
        lights_off = name in {"away", "vacation", "sleep"} or "lights off" in text or "keep the lights off" in text
        match = re.search(r"(?:temperature|thermostat|climate)(?:\s+\w+){0,3}?\s+(?:to|at)\s+(-?\d+(?:\.\d+)?)", text)
        temperature = float(match.group(1)) if match else (20.0 if name == "vacation" else None)
        if temperature is not None and not 5 <= temperature <= 30: temperature = None
        hours = re.search(r"(?:for|next)\s+(\d+)\s+hours?", text)
        days = re.search(r"(?:for|next)\s+(\d+)\s+days?", text)
        expires = self._clock() + (timedelta(hours=int(hours.group(1))) if hours else timedelta(days=int(days.group(1))) if days else timedelta(0))
        date_match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", text)
        weekday = next((index for index, day in enumerate(calendar.day_name) if re.search(rf"\b{day.casefold()}\b", text)), None)
        if date_match:
            expires = datetime.fromisoformat(date_match.group(1)).replace(tzinfo=self._clock().tzinfo) + timedelta(days=1)
        elif weekday is not None:
            delta = (weekday - self._clock().weekday()) % 7 or 7
            expires = (self._clock() + timedelta(days=delta)).replace(hour=23, minute=59, second=59, microsecond=0)
        expires_at = expires.isoformat() if hours or days or date_match or weekday is not None else None
        excluded = tuple(sorted(set(re.findall(r"\b(?:light|climate)\.[a-z0-9_]+", text)))) if "except" in text else ()
        presence = "presence simulation" in text or "simulate presence" in text
        if presence: lights_off = False
        return StewardshipMode(token_urlsafe(12), name, self._clock().isoformat(), expires_at, lights_off, temperature, excluded, (), True, presence)

    @staticmethod
    def _capture_restore_states(snapshot):
        values = []
        for entity in snapshot.entities:
            if not entity.action_allowed or entity.domain not in {"light", "climate"}:
                continue
            value = {"entity_id": entity.entity_id, "domain": entity.domain, "state": entity.state}
            if entity.domain == "climate" and entity.attributes.get("temperature") is not None:
                value["temperature"] = entity.attributes["temperature"]
            values.append(value)
        return tuple(values)

    async def _restore(self, mode):
        succeeded = failed = 0
        for item in mode.restore_states:
            domain = str(item.get("domain", "")); entity_id = str(item.get("entity_id", ""))
            if domain == "light" and item.get("state") in {"on", "off"}:
                proposal = HomeAssistantActionProposal("light", "turn_on" if item["state"] == "on" else "turn_off", (entity_id,), {}, "Stewardship: restore prior light state")
            elif domain == "climate" and item.get("temperature") is not None:
                proposal = HomeAssistantActionProposal("climate", "set_temperature", (entity_id,), {"temperature": item["temperature"]}, "Stewardship: restore prior climate target")
            else: continue
            if self._gateway.request(proposal).get("status") != "immediate_action": failed += 1; continue
            result = await self._gateway.execute_immediate(proposal)
            succeeded += len(result.get("succeeded", ())); failed += len(result.get("failed", ()))
        return succeeded, failed

    @staticmethod
    def _exceptions(mode, snapshot):
        if not mode.monitor_exceptions: return ()
        exceptions = []
        safety = {"smoke", "gas", "moisture", "water", "carbon_monoxide"}
        perimeter = {"door", "window", "garage_door", "opening"}
        for entity in snapshot.entities:
            if entity.entity_id in mode.excluded_entities: continue
            if entity.state == "on" and entity.device_class in safety | perimeter:
                exceptions.append((entity.entity_id, f"{entity.friendly_name} is active"))
            elif entity.domain == "lock" and entity.state == "unlocked" and mode.name in {"away", "vacation", "sleep"}:
                exceptions.append((entity.entity_id, f"{entity.friendly_name} is unlocked"))
            elif entity.state == "unavailable" and entity.domain in {"binary_sensor", "lock", "climate", "light"}:
                exceptions.append((entity.entity_id, f"{entity.friendly_name} is unavailable"))
        return tuple(exceptions)

    async def _notify_exceptions(self, mode, exceptions):
        fresh = tuple(item for item in exceptions if self.store.claim_alert(f"{mode.mode_id}:{item[0]}:{item[1]}", self._clock()))
        if not fresh: return 0
        self.store.audit("exceptions_detected", {"mode": mode.name, "exceptions": [message for _entity, message in fresh]}, self._clock())
        call_service = getattr(self._client, "call_service", None)
        if callable(call_service):
            try:
                await call_service("persistent_notification", "create", {"title": "Jarvis stewardship alert", "message": "\n".join(message for _entity, message in fresh), "notification_id": f"jarvis_stewardship_{mode.mode_id}"})
            except Exception:
                self.store.audit("exception_notification_failed", {"mode": mode.name}, self._clock())
        return len(fresh)

    @staticmethod
    def _temperature_differs(attributes, target):
        try: return abs(float(attributes.get("temperature")) - target) >= 0.1
        except (TypeError, ValueError): return True

    @staticmethod
    def _is_interior_light(entity):
        description = " ".join(filter(None, (entity.entity_id, entity.friendly_name, entity.area_name))).casefold()
        exterior_terms = (
            "exterior", "outdoor", "outside", "garden", "driveway", "terrace",
            "balcony", "porch", "facade", "carport", "yard",
        )
        return not any(term in description for term in exterior_terms)

    @staticmethod
    def _is_mode_request(text):
        return any(phrase in text for phrase in (
            "vacation mode", "away mode", "sleep mode", "home mode", "stewardship mode",
            "going on vacation", "going on holiday", "off on vacation", "off on holiday",
            "leaving for vacation", "leaving for holiday", "i am travelling", "i'm travelling",
            "im travelling", "i am traveling", "i'm traveling", "im traveling",
            "watch the house while", "monitor the house while", "i am leaving", "i'm leaving",
            "im leaving", "we are leaving", "we're leaving", "were leaving", "leaving home",
            "heading out", "going out", "we are going out", "we're going out", "were going out",
            "going away", "we are going away", "we're going away", "were going away",
            "going to bed", "i am going to bed", "i'm going to bed", "im going to bed",
            "we are going to bed", "we're going to bed", "were going to bed", "good night",
            "goodnight", "bedtime",
        ))

    @staticmethod
    def _infer_mode(text):
        if any(phrase in text for phrase in (
            "vacation", "holiday", "travelling", "traveling", "going away", "leaving for",
        )):
            return "vacation"
        if any(phrase in text for phrase in (
            "sleep", "going to bed", "good night", "goodnight", "bedtime",
        )):
            return "sleep"
        if any(phrase in text for phrase in (
            "away", "leaving", "leaving home", "heading out", "going out",
        )):
            return "away"
        return "home" if "home mode" in text else "custom"

    @staticmethod
    def _is_return_home(text):
        exact = {
            "cancel stewardship mode", "stop stewardship mode", "end stewardship mode",
            "end vacation mode", "end away mode", "return home", "back home",
            "i am home", "i'm home", "im home", "i am back home", "i'm back home",
            "im back home", "i am back", "i'm back", "im back", "we are home",
            "we're home", "were home", "we are back home", "we're back home",
            "home again", "back from vacation", "back from holiday",
        }
        return text in exact or bool(re.fullmatch(
            r"(?:hi jarvis,?\s+)?(?:i(?: am|'m|m)|we(?: are|'re|re))\s+(?:back\s+)?home(?:\s+now)?",
            text,
        ))

    @staticmethod
    def _is_morning_return(text):
        return text in {
            "good morning", "morning", "i am awake", "i'm awake", "im awake",
            "we are awake", "we're awake", "were awake", "wake up the house",
            "start the morning", "start morning mode",
        }

    @staticmethod
    def _chunks(values, size=20):
        return tuple(values[index:index + size] for index in range(0, len(values), size))
