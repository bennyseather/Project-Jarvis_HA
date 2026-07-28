"""Durable, replaceable reflection storage without retained deletion history."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from jarvis.models.reflection import ReflectionKind, ReflectionRecord


class SQLiteReflectionStore:
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
            if version > 3:
                raise RuntimeError(f"Unsupported database schema version: {version}")
            self._connection.execute(
                """CREATE TABLE IF NOT EXISTS reflection_records (
                    record_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL
                )"""
            )
            if version < 3:
                self._connection.execute("UPDATE schema_version SET version=3")

    def list_records(self) -> tuple[ReflectionRecord, ...]:
        rows = self._connection.execute(
            "SELECT payload FROM reflection_records ORDER BY record_id"
        ).fetchall()
        return tuple(self._decode(json.loads(row[0])) for row in rows)

    def replace_all(self, records: tuple[ReflectionRecord, ...]) -> None:
        payloads = tuple((record.reflection_id, self._encode(record)) for record in records)
        with self._connection:
            self._connection.execute("DELETE FROM reflection_records")
            self._connection.executemany(
                "INSERT INTO reflection_records(record_id, payload) VALUES (?, ?)",
                payloads,
            )

    def clear(self) -> None:
        with self._connection:
            self._connection.execute("DELETE FROM reflection_records")

    def close(self) -> None:
        self._connection.close()

    @staticmethod
    def _encode(record: ReflectionRecord) -> str:
        return json.dumps({
            "reflection_id": record.reflection_id,
            "kind": record.kind.value,
            "subject": record.subject,
            "content": record.content,
            "confidence": record.confidence,
            "source_memory_ids": list(record.source_memory_ids),
            "source_conversation_ids": list(record.source_conversation_ids),
            "sensitive": record.sensitive,
            "created_at": record.created_at.isoformat(),
            "updated_at": record.updated_at.isoformat(),
        }, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def _decode(value: dict) -> ReflectionRecord:
        from datetime import datetime
        return ReflectionRecord(
            value["reflection_id"],
            ReflectionKind(value["kind"]),
            value["subject"],
            value["content"],
            float(value["confidence"]),
            tuple(value["source_memory_ids"]),
            tuple(value["source_conversation_ids"]),
            bool(value["sensitive"]),
            datetime.fromisoformat(value["created_at"]),
            datetime.fromisoformat(value["updated_at"]),
        )
