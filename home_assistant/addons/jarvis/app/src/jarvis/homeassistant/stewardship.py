"""Durable, policy-controlled whole-home stewardship modes."""
from __future__ import annotations

import json
import re
import sqlite3
import calendar
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from secrets import token_urlsafe

from jarvis.models.home_assistant_gateway import HomeAssistantActionProposal


@dataclass(frozen=True, slots=True)
class StewardshipPolicy:
    enabled: bool = True
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
        if not isinstance(enabled, bool):
            raise ValueError("stewardship.enabled must be a boolean")
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
        return cls(enabled=enabled, **values)


@dataclass(frozen=True, slots=True)
class StewardshipMode:
    mode_id: str
    name: str
    activated_at: str
    expires_at: str | None
    lights_off: bool
    climate_temperature: float | None
    excluded_entities: tuple[str, ...]


class SQLiteStewardshipStore:
    def __init__(self, database_path: str | Path, *, audit_limit=100):
        path = Path(database_path); path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(path)
        self.audit_limit = audit_limit
        with self._connection:
            self._connection.execute("CREATE TABLE IF NOT EXISTS stewardship_state (slot INTEGER PRIMARY KEY CHECK(slot=1), payload TEXT NOT NULL)")
            self._connection.execute("CREATE TABLE IF NOT EXISTS stewardship_audit (occurred_at TEXT NOT NULL, event TEXT NOT NULL, payload TEXT NOT NULL)")

    def active(self):
        row = self._connection.execute("SELECT payload FROM stewardship_state WHERE slot=1").fetchone()
        if row is None: return None
        value = json.loads(row[0]); value["excluded_entities"] = tuple(value.get("excluded_entities", ()))
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

    def close(self): self._connection.close()


class StewardshipController:
    """Preview, activate, reconcile and cancel bounded home modes."""
    _MODES = {"home", "away", "vacation", "custom"}

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
        if normalized in {"cancel stewardship mode", "stop stewardship mode", "end vacation mode", "return home", "i am home"}:
            return await self.cancel()
        if not self._is_mode_request(normalized): return None
        mode = self._parse(normalized)
        try: snapshot = self._assembler.assemble(await self._client.get_states(), captured_at=self._clock())
        except Exception: return {"status": "unavailable", "message": "Home Assistant data is unavailable."}
        plan = self._plan(mode, snapshot)
        if isinstance(plan, dict): return plan
        token = token_urlsafe(24)
        self._pending[token] = (self._clock() + timedelta(seconds=self.policy.confirmation_ttl_seconds), mode)
        return {"status": "requires_confirmation", "token": token, "summary": plan, "risk": "stewardship_confirmation_required", "action_payload": {"kind": "stewardship_mode", "conversation_id": conversation_id}}

    async def confirm(self, token, payload):
        pending = self._pending.pop(token, None)
        if pending is None or pending[0] < self._clock() or payload.get("kind") != "stewardship_mode":
            return {"status": "forbidden", "message": "Stewardship confirmation is invalid or expired."}
        mode = pending[1]; self.store.save(mode)
        self.store.audit("activated", {"mode": mode.name, "mode_id": mode.mode_id}, self._clock())
        result = await self.reconcile()
        return {"status": result["status"], "message": f"{mode.name.title()} stewardship mode is active. {result['message']}"}

    def status(self):
        mode = self.store.active()
        if mode is None: return {"status": "success", "message": "No stewardship mode is active."}
        expiry = "until cancelled" if mode.expires_at is None else f"until {mode.expires_at}"
        temperature = "no climate target" if mode.climate_temperature is None else f"climate at {mode.climate_temperature:.1f} degrees"
        return {"status": "success", "message": f"{mode.name.title()} mode is active {expiry}: lights {'off' if mode.lights_off else 'unchanged'}, {temperature}, {len(mode.excluded_entities)} exclusions."}

    async def cancel(self):
        mode = self.store.active()
        if mode is None: return {"status": "success", "message": "No stewardship mode is active."}
        self.store.clear(); self.store.audit("cancelled", {"mode": mode.name, "mode_id": mode.mode_id}, self._clock())
        return {"status": "success", "message": f"{mode.name.title()} stewardship mode has ended. Devices remain in their current Home Assistant state."}

    async def reconcile(self):
        mode = self.store.active()
        if mode is None: return {"status": "success", "message": "No reconciliation was required."}
        if mode.expires_at and datetime.fromisoformat(mode.expires_at) <= self._clock():
            self.store.clear(); self.store.audit("expired", {"mode": mode.name}, self._clock())
            return {"status": "success", "message": f"{mode.name.title()} mode expired safely."}
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
        self.store.audit("reconciled", {"mode": mode.name, "succeeded": succeeded, "failed": failed, "skipped": skipped}, self._clock())
        status = "success" if not failed else "unavailable"
        return {"status": status, "message": f"Reconciliation complete: {succeeded} corrected, {skipped} policy-skipped, {failed} unavailable."}

    def _plan(self, mode, snapshot):
        proposals = self._proposals(mode, snapshot)
        count = sum(len(item.entity_ids) for item in proposals)
        if count > self.policy.maximum_targets:
            return {"status": "clarification_required", "message": f"That mode affects {count} entities; narrow it to {self.policy.maximum_targets} or fewer."}
        details = []
        if mode.lights_off: details.append("keep authorized lights off")
        if mode.climate_temperature is not None: details.append(f"keep authorized climate entities at {mode.climate_temperature:.1f} degrees")
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
        return proposals

    def _parse(self, text):
        name = next((item for item in ("vacation", "away", "home", "custom") if item in text), "custom")
        lights_off = name in {"away", "vacation"} or "lights off" in text or "keep the lights off" in text
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
        return StewardshipMode(token_urlsafe(12), name, self._clock().isoformat(), expires_at, lights_off, temperature, excluded)

    @staticmethod
    def _temperature_differs(attributes, target):
        try: return abs(float(attributes.get("temperature")) - target) >= 0.1
        except (TypeError, ValueError): return True

    @staticmethod
    def _is_mode_request(text):
        return any(phrase in text for phrase in ("vacation mode", "away mode", "home mode", "stewardship mode", "going on vacation", "going on holiday", "i am travelling", "i'm travelling", "i am traveling", "i'm traveling", "watch the house while", "monitor the house while"))

    @staticmethod
    def _chunks(values, size=20):
        return tuple(values[index:index + size] for index in range(0, len(values), size))
