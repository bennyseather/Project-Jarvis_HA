"""Durable suggestion and suppression storage with hard-delete controls."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from jarvis.models.proactive import (
    ProactiveSuggestion,
    ProactiveSuggestionKind,
    ProactiveSuggestionStatus,
)


class SQLiteProactiveStore:
    def __init__(self, database_path: str | Path) -> None:
        path = Path(database_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(path)
        with self._connection:
            self._connection.execute(
                "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)"
            )
            if self._connection.execute(
                "SELECT COUNT(*) FROM schema_version"
            ).fetchone()[0] == 0:
                self._connection.execute("INSERT INTO schema_version VALUES (1)")
            version = int(self._connection.execute(
                "SELECT version FROM schema_version LIMIT 1"
            ).fetchone()[0])
            if version > 4:
                raise RuntimeError(f"Unsupported database schema version: {version}")
            self._connection.execute(
                """CREATE TABLE IF NOT EXISTS proactive_suggestions (
                    suggestion_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL
                )"""
            )
            self._connection.execute(
                """CREATE TABLE IF NOT EXISTS proactive_suppressions (
                    subject TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL
                )"""
            )
            if version < 4:
                self._connection.execute("UPDATE schema_version SET version=4")

    def upsert(self, suggestion: ProactiveSuggestion) -> None:
        payload = json.dumps(
            self._encode(suggestion), sort_keys=True, separators=(",", ":")
        )
        with self._connection:
            self._connection.execute(
                """INSERT INTO proactive_suggestions(suggestion_id, payload)
                   VALUES (?, ?)
                   ON CONFLICT(suggestion_id) DO UPDATE SET payload=excluded.payload""",
                (suggestion.suggestion_id, payload),
            )

    def get(self, suggestion_id: str) -> ProactiveSuggestion | None:
        row = self._connection.execute(
            "SELECT payload FROM proactive_suggestions WHERE suggestion_id=?",
            (suggestion_id,),
        ).fetchone()
        return None if row is None else self._decode(json.loads(row[0]))

    def list_records(self) -> tuple[ProactiveSuggestion, ...]:
        return tuple(
            self._decode(json.loads(row[0]))
            for row in self._connection.execute(
                "SELECT payload FROM proactive_suggestions ORDER BY suggestion_id"
            )
        )

    def delete(self, suggestion_id: str) -> None:
        with self._connection:
            self._connection.execute(
                "DELETE FROM proactive_suggestions WHERE suggestion_id=?",
                (suggestion_id,),
            )

    def clear(self) -> None:
        with self._connection:
            self._connection.execute("DELETE FROM proactive_suggestions")

    def suppress(self, subject: str, created_at: datetime) -> None:
        with self._connection:
            self._connection.execute(
                "INSERT OR REPLACE INTO proactive_suppressions VALUES (?, ?)",
                (subject, created_at.isoformat()),
            )

    def unsuppress(self, subject: str) -> None:
        with self._connection:
            self._connection.execute(
                "DELETE FROM proactive_suppressions WHERE subject=?", (subject,)
            )

    def is_suppressed(self, subject: str) -> bool:
        return self._connection.execute(
            "SELECT 1 FROM proactive_suppressions WHERE subject=?", (subject,)
        ).fetchone() is not None

    def suppressions(self) -> tuple[str, ...]:
        return tuple(
            row[0] for row in self._connection.execute(
                "SELECT subject FROM proactive_suppressions ORDER BY subject"
            )
        )

    def clear_suppressions(self) -> None:
        with self._connection:
            self._connection.execute("DELETE FROM proactive_suppressions")

    def close(self) -> None:
        self._connection.close()

    @staticmethod
    def _encode(record: ProactiveSuggestion) -> dict[str, object]:
        return {
            "suggestion_id": record.suggestion_id,
            "kind": record.kind.value,
            "subject": record.subject,
            "message": record.message,
            "reason": record.reason,
            "confidence": record.confidence,
            "source_ids": list(record.source_ids),
            "sensitive": record.sensitive,
            "action": None if record.action is None else dict(record.action),
            "status": record.status.value,
            "created_at": record.created_at.isoformat(),
            "updated_at": record.updated_at.isoformat(),
            "expires_at": record.expires_at.isoformat(),
            "snoozed_until": (
                None
                if record.snoozed_until is None
                else record.snoozed_until.isoformat()
            ),
            "delivered_channels": list(record.delivered_channels),
            "metadata": dict(record.metadata),
        }

    @staticmethod
    def _decode(value: dict[str, object]) -> ProactiveSuggestion:
        from datetime import datetime

        return ProactiveSuggestion(
            suggestion_id=str(value["suggestion_id"]),
            kind=ProactiveSuggestionKind(str(value["kind"])),
            subject=str(value["subject"]),
            message=str(value["message"]),
            reason=str(value["reason"]),
            confidence=float(value["confidence"]),
            source_ids=tuple(value.get("source_ids", ())),
            sensitive=bool(value.get("sensitive", False)),
            action=value.get("action"),
            status=ProactiveSuggestionStatus(str(value["status"])),
            created_at=datetime.fromisoformat(str(value["created_at"])),
            updated_at=datetime.fromisoformat(str(value["updated_at"])),
            expires_at=datetime.fromisoformat(str(value["expires_at"])),
            snoozed_until=(
                None
                if value.get("snoozed_until") is None
                else datetime.fromisoformat(str(value["snoozed_until"]))
            ),
            delivered_channels=tuple(value.get("delivered_channels", ())),
            metadata=dict(value.get("metadata", {})),
        )
