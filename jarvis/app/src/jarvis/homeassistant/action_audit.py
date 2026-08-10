"""Privacy-bounded durable audit for confirmed Home Assistant actions."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


@dataclass(frozen=True)
class ConfirmedActionAuditRecord:
    """The intentionally small record retained after a confirmation attempt."""

    audit_id: str
    occurred_at: datetime
    domain: str
    service: str
    entity_ids: tuple[str, ...]
    outcome: str
    reason_code: str | None = None


class SQLiteConfirmedActionAuditStore:
    """Append-only action audit that deliberately has no free-form text fields."""

    def __init__(self, database_path: str | Path, clock=None) -> None:
        path = Path(database_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(path)
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS confirmed_action_audit "
            "(audit_id TEXT PRIMARY KEY, occurred_at TEXT NOT NULL, payload TEXT NOT NULL)"
        )
        self._connection.commit()

    def record(self, domain: str, service: str, entity_ids: tuple[str, ...], outcome: str,
               reason_code: str | None = None) -> ConfirmedActionAuditRecord:
        if outcome not in {"success", "forbidden", "unavailable"}:
            raise ValueError("audit outcome is invalid")
        if not domain or not service or not entity_ids:
            raise ValueError("audit records require an authorized service and entity")
        record = ConfirmedActionAuditRecord(
            uuid4().hex, self._clock(), domain, service, tuple(entity_ids), outcome, reason_code
        )
        payload = json.dumps({
            "domain": record.domain,
            "service": record.service,
            "entity_ids": list(record.entity_ids),
            "outcome": record.outcome,
            "reason_code": record.reason_code,
        }, sort_keys=True, separators=(",", ":"))
        self._connection.execute(
            "INSERT INTO confirmed_action_audit VALUES (?, ?, ?)",
            (record.audit_id, record.occurred_at.isoformat(), payload),
        )
        self._connection.commit()
        return record

    def recent(self, limit: int = 10) -> tuple[ConfirmedActionAuditRecord, ...]:
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 50:
            raise ValueError("audit limit must be an integer between 1 and 50")
        rows = self._connection.execute(
            "SELECT audit_id, occurred_at, payload FROM confirmed_action_audit "
            "ORDER BY occurred_at DESC, audit_id DESC LIMIT ?", (limit,)
        )
        return tuple(
            self._decode(row[0], row[1], row[2]) for row in rows
        )

    def close(self) -> None:
        self._connection.close()

    @staticmethod
    def _decode(audit_id: str, occurred_at: str, payload: str) -> ConfirmedActionAuditRecord:
        value = json.loads(payload)
        return ConfirmedActionAuditRecord(
            audit_id, datetime.fromisoformat(occurred_at), value["domain"], value["service"],
            tuple(value["entity_ids"]), value["outcome"], value.get("reason_code"),
        )
