"""Durable idempotency records for travel-to-calendar synchronization."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True, slots=True)
class TravelSyncRecord:
    identity: str
    content_hash: str
    calendar_event_id: str
    source_message_ids: tuple[str, ...]
    updated_at: datetime
    journey_reference: str = ""
    passenger_name: str = ""
    segment_reference: str = ""


class SQLiteTravelSyncStore:
    def __init__(self, database_path: str | Path) -> None:
        path = Path(database_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(path)
        with self._connection:
            self._connection.execute(
                """CREATE TABLE IF NOT EXISTS travel_calendar_sync (
                    identity TEXT PRIMARY KEY,
                    content_hash TEXT NOT NULL,
                    calendar_event_id TEXT NOT NULL,
                    source_message_ids TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    journey_reference TEXT NOT NULL DEFAULT '',
                    passenger_name TEXT NOT NULL DEFAULT '',
                    segment_reference TEXT NOT NULL DEFAULT ''
                )"""
            )
            columns = {
                row[1]
                for row in self._connection.execute(
                    "PRAGMA table_info(travel_calendar_sync)"
                )
            }
            for name in (
                "journey_reference",
                "passenger_name",
                "segment_reference",
            ):
                if name not in columns:
                    self._connection.execute(
                        f"ALTER TABLE travel_calendar_sync ADD COLUMN {name} "
                        "TEXT NOT NULL DEFAULT ''"
                    )

    def get(self, identity: str) -> TravelSyncRecord | None:
        row = self._connection.execute(
            """SELECT identity, content_hash, calendar_event_id,
                      source_message_ids, updated_at, journey_reference,
                      passenger_name, segment_reference
                 FROM travel_calendar_sync WHERE identity=?""",
            (identity,),
        ).fetchone()
        if row is None:
            return None
        return TravelSyncRecord(
            identity=row[0],
            content_hash=row[1],
            calendar_event_id=row[2],
            source_message_ids=tuple(json.loads(row[3])),
            updated_at=datetime.fromisoformat(row[4]),
            journey_reference=row[5],
            passenger_name=row[6],
            segment_reference=row[7],
        )

    def list_by_journey_reference(
        self, journey_reference: str, passenger_name: str
    ) -> tuple[TravelSyncRecord, ...]:
        rows = self._connection.execute(
            """SELECT identity, content_hash, calendar_event_id,
                      source_message_ids, updated_at, journey_reference,
                      passenger_name, segment_reference
                 FROM travel_calendar_sync
                WHERE journey_reference=? AND passenger_name=?
                ORDER BY segment_reference""",
            (journey_reference, passenger_name),
        ).fetchall()
        return tuple(
            TravelSyncRecord(
                identity=row[0],
                content_hash=row[1],
                calendar_event_id=row[2],
                source_message_ids=tuple(json.loads(row[3])),
                updated_at=datetime.fromisoformat(row[4]),
                journey_reference=row[5],
                passenger_name=row[6],
                segment_reference=row[7],
            )
            for row in rows
        )

    def upsert(self, record: TravelSyncRecord) -> None:
        with self._connection:
            self._connection.execute(
                """INSERT INTO travel_calendar_sync
                   (identity, content_hash, calendar_event_id,
                    source_message_ids, updated_at, journey_reference,
                    passenger_name, segment_reference)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(identity) DO UPDATE SET
                     content_hash=excluded.content_hash,
                     calendar_event_id=excluded.calendar_event_id,
                     source_message_ids=excluded.source_message_ids,
                     updated_at=excluded.updated_at,
                     journey_reference=excluded.journey_reference,
                     passenger_name=excluded.passenger_name,
                     segment_reference=excluded.segment_reference""",
                (
                    record.identity,
                    record.content_hash,
                    record.calendar_event_id,
                    json.dumps(sorted(set(record.source_message_ids))),
                    record.updated_at.isoformat(),
                    record.journey_reference,
                    record.passenger_name,
                    record.segment_reference,
                ),
            )

    def close(self) -> None:
        self._connection.close()
