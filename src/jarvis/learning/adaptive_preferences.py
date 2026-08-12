"""Durable, approval-gated adaptive household preference learning."""
from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from secrets import token_urlsafe


@dataclass(frozen=True, slots=True)
class AdaptiveLearningPolicy:
    enabled: bool = True
    evidence_threshold: int = 3
    minimum_confidence: float = 0.75
    stale_after_days: int = 90
    confirmation_ttl_seconds: int = 300
    maximum_preferences: int = 100
    audit_limit: int = 200

    @classmethod
    def from_config(cls, value):
        value = {} if value is None else value
        if not isinstance(value, dict):
            raise ValueError("adaptive_learning must be a mapping")
        enabled = value.get("enabled", True)
        if not isinstance(enabled, bool):
            raise ValueError("adaptive_learning.enabled must be a boolean")
        integers = {
            "evidence_threshold": (2, 10, 3),
            "stale_after_days": (7, 365, 90),
            "confirmation_ttl_seconds": (30, 600, 300),
            "maximum_preferences": (1, 500, 100),
            "audit_limit": (10, 1000, 200),
        }
        result = {}
        for name, (low, high, default) in integers.items():
            item = value.get(name, default)
            if isinstance(item, bool) or not isinstance(item, int) or not low <= item <= high:
                raise ValueError(f"adaptive_learning.{name} must be between {low} and {high}")
            result[name] = item
        confidence = value.get("minimum_confidence", 0.75)
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0.5 <= confidence <= 1.0:
            raise ValueError("adaptive_learning.minimum_confidence must be between 0.5 and 1.0")
        return cls(enabled=enabled, minimum_confidence=float(confidence), **result)


@dataclass(frozen=True, slots=True)
class AdaptivePreference:
    preference_id: str
    key: str
    category: str
    scope: str
    value: str
    evidence_count: int
    confidence: float
    status: str
    first_observed_at: str
    last_observed_at: str
    evidence: tuple[str, ...]


class SQLiteAdaptivePreferenceStore:
    def __init__(self, database_path: str | Path, *, audit_limit: int = 200):
        path = Path(database_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(path)
        self.audit_limit = audit_limit
        with self._connection:
            self._connection.execute(
                "CREATE TABLE IF NOT EXISTS adaptive_preferences "
                "(preference_id TEXT PRIMARY KEY, key TEXT UNIQUE NOT NULL, payload TEXT NOT NULL)"
            )
            self._connection.execute(
                "CREATE TABLE IF NOT EXISTS adaptive_preference_audit "
                "(occurred_at TEXT NOT NULL, event TEXT NOT NULL, preference_id TEXT, payload TEXT NOT NULL)"
            )

    def get_by_key(self, key):
        row = self._connection.execute(
            "SELECT payload FROM adaptive_preferences WHERE key=?", (key,)
        ).fetchone()
        return None if row is None else self._decode(row[0])

    def get(self, preference_id):
        row = self._connection.execute(
            "SELECT payload FROM adaptive_preferences WHERE preference_id=?", (preference_id,)
        ).fetchone()
        return None if row is None else self._decode(row[0])

    def save(self, preference):
        payload = json.dumps(asdict(preference), sort_keys=True, separators=(",", ":"))
        with self._connection:
            self._connection.execute(
                "INSERT OR REPLACE INTO adaptive_preferences VALUES (?,?,?)",
                (preference.preference_id, preference.key, payload),
            )
        return preference

    def list(self, status=None):
        rows = self._connection.execute(
            "SELECT payload FROM adaptive_preferences ORDER BY key"
        ).fetchall()
        values = tuple(self._decode(row[0]) for row in rows)
        return values if status is None else tuple(item for item in values if item.status == status)

    def delete(self, preference_id):
        with self._connection:
            return self._connection.execute(
                "DELETE FROM adaptive_preferences WHERE preference_id=?", (preference_id,)
            ).rowcount > 0

    def audit(self, event, preference_id, payload, now):
        with self._connection:
            self._connection.execute(
                "INSERT INTO adaptive_preference_audit VALUES (?,?,?,?)",
                (now.isoformat(), event, preference_id, json.dumps(payload, sort_keys=True)),
            )
            self._connection.execute(
                "DELETE FROM adaptive_preference_audit WHERE rowid NOT IN "
                "(SELECT rowid FROM adaptive_preference_audit ORDER BY occurred_at DESC,rowid DESC LIMIT ?)",
                (self.audit_limit,),
            )

    def close(self):
        self._connection.close()

    @staticmethod
    def _decode(payload):
        value = json.loads(payload)
        value["evidence"] = tuple(value.get("evidence", ()))
        return AdaptivePreference(**value)


class AdaptivePreferenceController:
    """Observe explicit patterns and promote them only after confirmation."""

    _FORBIDDEN = ("unlock", "alarm", "disarm", "credential", "password", "purchase", "spend")

    def __init__(self, store, policy, *, clock=None):
        self.store, self.policy = store, policy
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._pending = {}
        self._last_key = {}
        self._area_names = ()
        self._area_aliases = {}

    def set_area_references(self, area_names, aliases=None):
        """Install current HA area names and safely canonicalize stored scopes."""
        self._area_names = tuple(sorted({self._normalize_area(name) for name in area_names if name}))
        aliases = aliases or {}
        self._area_aliases = {
            self._normalize_area(alias): self._normalize_area(target)
            for alias, target in aliases.items()
            if alias and target
        }
        self._canonicalize_existing()

    def handle(self, text, conversation_id):
        if not self.policy.enabled:
            return None
        normalized = " ".join(text.casefold().strip(" .?!").split())
        if normalized in {"what have you learned", "what have you learned about me", "show learned preferences", "show preferences"}:
            return self.list_approved()
        if normalized.startswith("why did you learn") or normalized.startswith("why do you think"):
            return self.explain(normalized)
        if normalized.startswith("forget") and "preference" in normalized:
            return self.forget(normalized)
        correction = self._parse_correction(normalized, conversation_id)
        if correction is not None:
            return self._observe(*correction, text=text, conversation_id=conversation_id, correction=True)
        observation = self._parse_observation(normalized)
        if observation is None:
            return None
        return self._observe(*observation, text=text, conversation_id=conversation_id)

    def observe_outcome(self, text, result, conversation_id):
        """Learn from a completed preference-bearing action without replacing it."""
        if not self.policy.enabled or result.get("status") not in {
            "success", "action_done", "partial_success"
        }:
            return None
        normalized = " ".join(text.casefold().strip(" .?!").split())
        observation = self._parse_action_choice(normalized)
        if observation is None or any(term in normalized for term in self._FORBIDDEN):
            return None
        learning = self._observe(
            *observation, text=text, conversation_id=conversation_id, quiet=True
        )
        return None

    def confirm(self, token, payload):
        pending = self._pending.pop(token, None)
        if pending is None or pending[0] < self._clock() or payload.get("kind") != "adaptive_preference":
            return {"status": "forbidden", "message": "Learning confirmation is invalid or expired."}
        preference = self.store.get(pending[1])
        if preference is None or preference.status != "suggested":
            return {"status": "forbidden", "message": "That learning proposal is no longer available."}
        preference = self.store.save(replace(preference, status="approved"))
        self.store.audit("approved", preference.preference_id, {"key": preference.key, "value": preference.value}, self._clock())
        return {"status": "success", "message": f"Learned preference approved: {self._describe(preference)}."}

    def context(self):
        self._decay()
        return tuple(
            {"key": item.key, "category": item.category, "scope": item.scope, "value": item.value, "confidence": round(item.confidence, 2)}
            for item in self.store.list("approved")
        )

    def list_approved(self):
        items = self.store.list("approved")
        if not items:
            return {"status": "success", "message": "I have no approved learned preferences."}
        return {"status": "success", "message": "Approved learned preferences: " + "; ".join(self._describe(item) for item in items) + "."}

    def explain(self, text):
        item = self._best_match(text, self.store.list())
        if item is None:
            return {"status": "not_found", "message": "I found no matching learned preference."}
        evidence = "; ".join(item.evidence[-3:])
        return {"status": "success", "message": f"I observed this {item.evidence_count} times with {item.confidence:.0%} confidence. Evidence: {evidence}. Status: {item.status}."}

    def forget(self, text):
        item = self._best_match(text, self.store.list())
        if item is None:
            return {"status": "not_found", "message": "I found no matching learned preference."}
        self.store.delete(item.preference_id)
        self.store.audit("deleted", item.preference_id, {"key": item.key}, self._clock())
        return {"status": "success", "message": f"Forgotten: {self._describe(item)}."}

    def _observe(self, category, scope, value, *, text, conversation_id, correction=False, quiet=False):
        if any(term in text.casefold() for term in self._FORBIDDEN):
            return {"status": "forbidden", "message": "That category cannot be learned as a preference."}
        key = f"{category}.{scope}"
        now = self._clock()
        current = self.store.get_by_key(key)
        if current is not None and current.value != value:
            if not correction:
                return {"status": "clarification_required", "message": f"That conflicts with the existing {self._describe(current)}. Say ‘that is wrong, use {value} instead’ to correct it."}
            current = replace(current, value=value, evidence_count=1, confidence=0.55, status="observed", first_observed_at=now.isoformat(), last_observed_at=now.isoformat(), evidence=(text[:200],))
            self.store.save(current)
            self.store.audit("corrected", current.preference_id, {"key": key, "value": value}, now)
            self._last_key[conversation_id] = key
            return {"status": "success", "message": f"Correction recorded. I will require three consistent observations before using {value}."}
        if current is None:
            if len(self.store.list()) >= self.policy.maximum_preferences:
                return {"status": "forbidden", "message": "The learned-preference limit has been reached."}
            current = AdaptivePreference(token_urlsafe(12), key, category, scope, value, 0, 0.0, "observed", now.isoformat(), now.isoformat(), ())
        count = current.evidence_count + 1
        confidence = min(0.95, 0.35 + 0.2 * count)
        evidence = (current.evidence + (text[:200],))[-5:]
        status = current.status
        automatically_approved = (
            status != "approved"
            and count >= self.policy.evidence_threshold
            and confidence >= self.policy.minimum_confidence
        )
        if automatically_approved:
            status = "approved"
        current = self.store.save(replace(current, evidence_count=count, confidence=confidence, status=status, last_observed_at=now.isoformat(), evidence=evidence))
        self.store.audit("observed", current.preference_id, {"key": key, "count": count, "confidence": confidence}, now)
        self._last_key[conversation_id] = key
        if status == "approved":
            if automatically_approved:
                self.store.audit("automatically_approved", current.preference_id, {"key": key, "value": value, "evidence_count": count}, now)
                return {"status": "success", "message": f"Preference automatically approved after {count} consistent observations: {self._describe(current)}."}
            return {"status": "success", "message": f"That matches the approved preference: {self._describe(current)}."}
        if status == "suggested":
            token = token_urlsafe(24)
            self._pending[token] = (now + timedelta(seconds=self.policy.confirmation_ttl_seconds), current.preference_id)
            return {"status": "requires_confirmation", "token": token, "summary": f"Learn {self._describe(current)} based on {count} observations", "risk": "preference_learning_confirmation_required", "action_payload": {"kind": "adaptive_preference", "preference_id": current.preference_id}}
        if quiet:
            return {"status": "observed"}
        return {"status": "success", "message": f"Preference observation recorded ({count} of {self.policy.evidence_threshold}); it will not affect Jarvis until three consistent observations are recorded."}

    def _decay(self):
        cutoff = self._clock() - timedelta(days=self.policy.stale_after_days)
        for item in self.store.list():
            if item.status == "approved" or datetime.fromisoformat(item.last_observed_at) >= cutoff:
                continue
            count = max(0, item.evidence_count - 1)
            confidence = max(0.0, item.confidence - 0.2)
            status = "observed" if count else "stale"
            self.store.save(replace(item, evidence_count=count, confidence=confidence, status=status))

    def _parse_observation(self, text):
        temperature = re.search(
            r"\b(?:i prefer|i like|i usually (?:set|keep))\s+(?:the\s+)?"
            r"([a-z0-9 _-]+?)(?:\s+temperature)?\s+"
            r"(?:at|to(?:\s+be)?|on)\s+(-?\d+(?:\.\d+)?)\s*degrees?\b",
            text,
        )
        if temperature:
            return "temperature", self._scope(temperature.group(1)), f"{float(temperature.group(2)):.1f}"
        lighting = re.search(r"\b(?:i prefer|i like|i usually (?:set|keep))\s+(?:the\s+)?([a-z0-9 _-]+?)\s+(?:lights?\s+)?(?:at|to|on)\s+(\d{1,3})\s*(?:percent|%)\b", text)
        if lighting and 0 <= int(lighting.group(2)) <= 100:
            return "lighting", self._scope(lighting.group(1)), str(int(lighting.group(2)))
        return None

    def _parse_correction(self, text, conversation_id):
        if not any(phrase in text for phrase in ("that is wrong", "use ", "instead")):
            return None
        value = re.search(r"\b(-?\d+(?:\.\d+)?)\s*(degrees?|percent|%)?\b", text)
        key = self._last_key.get(conversation_id)
        if value is None or key is None:
            return None
        category, scope = key.split(".", 1)
        formatted = f"{float(value.group(1)):.1f}" if category == "temperature" else str(int(float(value.group(1))))
        return category, scope, formatted

    def _parse_action_choice(self, text):
        temperature = re.search(
            r"\b(?:set|keep|change)\s+(?:the\s+)?([a-z0-9 _-]+?)"
            r"(?:\s+temperature)?\s+(?:at|to)\s+(-?\d+(?:\.\d+)?)\s*degrees?\b",
            text,
        )
        if temperature:
            return "temperature", self._scope(temperature.group(1)), f"{float(temperature.group(2)):.1f}"
        lighting = re.search(
            r"\b(?:set|keep|change)\s+(?:the\s+)?([a-z0-9 _-]+?)"
            r"(?:\s+lights?)?\s+(?:at|to)\s+(\d{1,3})\s*(?:percent|%)\b",
            text,
        )
        if lighting and 0 <= int(lighting.group(2)) <= 100:
            return "lighting", self._scope(lighting.group(1)), str(int(lighting.group(2)))
        return None

    def _scope(self, value):
        canonical = self._canonical_area(value)
        normalized = canonical or self._normalize_area(value)
        return re.sub(r"[^a-z0-9]+", "_", normalized).strip("_")

    def _canonical_area(self, value):
        normalized = self._normalize_area(value)
        if not self._area_names:
            return normalized
        normalized = self._area_aliases.get(normalized, normalized)
        if normalized in self._area_names:
            return normalized
        words = set(normalized.split())
        candidates = tuple(
            area for area in self._area_names
            if words <= set(area.split()) or set(area.split()) <= words
        )
        return candidates[0] if len(candidates) == 1 else None

    @staticmethod
    def _normalize_area(value):
        words = re.sub(r"[^a-z0-9]+", " ", str(value).casefold()).split()
        while words and words[0] in {"my", "the", "our", "a", "an"}:
            words.pop(0)
        while words and words[-1] == "area":
            words.pop()
        return " ".join(words)

    def _canonicalize_existing(self):
        for item in self.store.list():
            canonical = self._canonical_area(item.scope.replace("_", " "))
            if canonical is None:
                continue
            scope = re.sub(r"[^a-z0-9]+", "_", canonical).strip("_")
            key = f"{item.category}.{scope}"
            if key == item.key:
                continue
            existing = self.store.get_by_key(key)
            if existing is not None and existing.value != item.value:
                continue
            if existing is None:
                self.store.delete(item.preference_id)
                self.store.save(replace(item, key=key, scope=scope))
                continue
            merged = replace(
                existing,
                evidence_count=max(existing.evidence_count, item.evidence_count),
                confidence=max(existing.confidence, item.confidence),
                status="approved" if "approved" in {existing.status, item.status} else existing.status,
                first_observed_at=min(existing.first_observed_at, item.first_observed_at),
                last_observed_at=max(existing.last_observed_at, item.last_observed_at),
                evidence=(existing.evidence + item.evidence)[-5:],
            )
            self.store.delete(item.preference_id)
            self.store.save(merged)

    @staticmethod
    def _describe(item):
        unit = "degrees" if item.category == "temperature" else "percent"
        return f"{item.scope.replace('_', ' ')} {item.category} at {item.value} {unit}"

    @staticmethod
    def _best_match(text, items):
        words = set(re.findall(r"[a-z0-9]+", text.casefold())) - {"why", "did", "you", "learn", "forget", "preference", "about", "that"}
        ranked = sorted(items, key=lambda item: len(words & set(item.key.replace("_", ".").split("."))), reverse=True)
        return ranked[0] if ranked and len(words & set(ranked[0].key.replace("_", ".").split("."))) else None
