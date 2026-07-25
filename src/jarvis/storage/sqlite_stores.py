"""Schema-managed SQLite stores for explicit Memory and curated Knowledge."""
from __future__ import annotations

import json
import sqlite3
from copy import deepcopy
from pathlib import Path

from jarvis.memory.in_memory_store import InMemoryMemoryStore
from jarvis.memory.store import DuplicateMemoryError, InvalidMemoryOperationError, MemoryNotFoundError
from jarvis.knowledge.in_memory_store import InMemoryKnowledgeStore
from jarvis.knowledge.store import DuplicateKnowledgeError, InvalidKnowledgeOperationError, KnowledgeNotFoundError
from jarvis.models.memory import MemoryConsentLevel, MemoryRecord, MemorySource, MemoryStatus, MemoryType
from jarvis.models.knowledge import KnowledgeRecord, KnowledgeSource, KnowledgeStatus, KnowledgeType


class _SQLiteStore:
    def __init__(self, database_path: str | Path) -> None:
        self._path = Path(database_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self._path)
        self._connection.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
        if self._connection.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0] == 0:
            self._connection.execute("INSERT INTO schema_version VALUES (1)")
        self._connection.commit()

    def close(self) -> None:
        self._connection.close()

    def _create_table(self, name: str) -> None:
        self._connection.execute(f"CREATE TABLE IF NOT EXISTS {name} (record_id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
        self._connection.commit()

    @staticmethod
    def _dump(value: dict) -> str:
        try:
            return json.dumps(value, sort_keys=True, separators=(",", ":"))
        except (TypeError, ValueError) as error:
            raise ValueError("record metadata must be JSON-compatible") from error


class SQLiteMemoryStore(_SQLiteStore):
    def __init__(self, database_path: str | Path) -> None:
        super().__init__(database_path)
        self._create_table("memory_records")

    def create(self, record: MemoryRecord) -> MemoryRecord:
        InMemoryMemoryStore._validate(record)
        try:
            self._connection.execute("INSERT INTO memory_records VALUES (?, ?)", (record.memory_id, self._dump(self._encode(record))))
            self._connection.commit()
        except ValueError as error:
            raise InvalidMemoryOperationError(str(error)) from error
        except sqlite3.IntegrityError as error:
            raise DuplicateMemoryError(f"Memory already exists: {record.memory_id}") from error
        return deepcopy(record)

    def get(self, memory_id: str) -> MemoryRecord:
        row = self._connection.execute("SELECT payload FROM memory_records WHERE record_id = ?", (memory_id,)).fetchone()
        if row is None:
            raise MemoryNotFoundError(f"Memory not found: {memory_id}")
        return self._decode(json.loads(row[0]))

    def list_records(self) -> tuple[MemoryRecord, ...]:
        return tuple(self._decode(json.loads(row[0])) for row in self._connection.execute("SELECT payload FROM memory_records ORDER BY record_id"))

    def update(self, record: MemoryRecord) -> MemoryRecord:
        InMemoryMemoryStore._validate(record)
        try:
            cursor = self._connection.execute("UPDATE memory_records SET payload = ? WHERE record_id = ?", (self._dump(self._encode(record)), record.memory_id))
        except ValueError as error:
            raise InvalidMemoryOperationError(str(error)) from error
        self._connection.commit()
        if cursor.rowcount == 0:
            raise MemoryNotFoundError(f"Memory not found: {record.memory_id}")
        return deepcopy(record)

    def delete(self, memory_id: str) -> None:
        cursor = self._connection.execute("DELETE FROM memory_records WHERE record_id = ?", (memory_id,))
        self._connection.commit()
        if cursor.rowcount == 0:
            raise MemoryNotFoundError(f"Memory not found: {memory_id}")

    def clear(self) -> None:
        self._connection.execute("DELETE FROM memory_records")
        self._connection.commit()

    def exists(self, memory_id: str) -> bool:
        return self._connection.execute("SELECT 1 FROM memory_records WHERE record_id = ?", (memory_id,)).fetchone() is not None

    @staticmethod
    def _encode(record: MemoryRecord) -> dict:
        return {"memory_id":record.memory_id,"memory_type":record.memory_type.value,"content":record.content,"source":record.source.value,"consent_level":record.consent_level.value,"created_at":record.created_at.isoformat(),"updated_at":record.updated_at.isoformat(),"source_request_id":record.source_request_id,"expires_at":None if record.expires_at is None else record.expires_at.isoformat(),"importance":record.importance,"confidence":record.confidence,"tags":list(record.tags),"status":record.status.value,"metadata":dict(record.metadata)}

    @staticmethod
    def _decode(value: dict) -> MemoryRecord:
        from datetime import datetime
        return MemoryRecord(value["memory_id"],MemoryType(value["memory_type"]),value["content"],MemorySource(value["source"]),MemoryConsentLevel(value["consent_level"]),datetime.fromisoformat(value["created_at"]),datetime.fromisoformat(value["updated_at"]),value["source_request_id"],None if value["expires_at"] is None else datetime.fromisoformat(value["expires_at"]),value["importance"],value["confidence"],tuple(value["tags"]),MemoryStatus(value["status"]),value["metadata"])


class SQLiteKnowledgeStore(_SQLiteStore):
    def __init__(self, database_path: str | Path) -> None:
        super().__init__(database_path)
        self._create_table("knowledge_records")

    def create(self, record: KnowledgeRecord) -> KnowledgeRecord:
        InMemoryKnowledgeStore._validate(record)
        try:
            self._connection.execute("INSERT INTO knowledge_records VALUES (?, ?)", (record.knowledge_id, self._dump(self._encode(record))))
            self._connection.commit()
        except ValueError as error:
            raise InvalidKnowledgeOperationError(str(error)) from error
        except sqlite3.IntegrityError as error:
            raise DuplicateKnowledgeError(f"Knowledge already exists: {record.knowledge_id}") from error
        return deepcopy(record)

    def get(self, knowledge_id: str) -> KnowledgeRecord:
        row = self._connection.execute("SELECT payload FROM knowledge_records WHERE record_id = ?", (knowledge_id,)).fetchone()
        if row is None: raise KnowledgeNotFoundError(f"Knowledge not found: {knowledge_id}")
        return self._decode(json.loads(row[0]))

    def list_records(self) -> tuple[KnowledgeRecord, ...]:
        return tuple(self._decode(json.loads(row[0])) for row in self._connection.execute("SELECT payload FROM knowledge_records ORDER BY record_id"))

    def update(self, record: KnowledgeRecord) -> KnowledgeRecord:
        InMemoryKnowledgeStore._validate(record)
        try:
            cursor = self._connection.execute("UPDATE knowledge_records SET payload = ? WHERE record_id = ?", (self._dump(self._encode(record)), record.knowledge_id))
        except ValueError as error:
            raise InvalidKnowledgeOperationError(str(error)) from error
        self._connection.commit()
        if cursor.rowcount == 0: raise KnowledgeNotFoundError(f"Knowledge not found: {record.knowledge_id}")
        return deepcopy(record)

    def delete(self, knowledge_id: str) -> None:
        cursor = self._connection.execute("DELETE FROM knowledge_records WHERE record_id = ?", (knowledge_id,))
        self._connection.commit()
        if cursor.rowcount == 0: raise KnowledgeNotFoundError(f"Knowledge not found: {knowledge_id}")

    def clear(self) -> None:
        self._connection.execute("DELETE FROM knowledge_records"); self._connection.commit()

    def exists(self, knowledge_id: str) -> bool:
        return self._connection.execute("SELECT 1 FROM knowledge_records WHERE record_id = ?", (knowledge_id,)).fetchone() is not None

    @staticmethod
    def _encode(record: KnowledgeRecord) -> dict:
        return {"knowledge_id":record.knowledge_id,"knowledge_type":record.knowledge_type.value,"content":record.content,"source":record.source.value,"created_at":record.created_at.isoformat(),"updated_at":record.updated_at.isoformat(),"source_request_id":record.source_request_id,"title":record.title,"tags":list(record.tags),"status":record.status.value,"metadata":dict(record.metadata)}

    @staticmethod
    def _decode(value: dict) -> KnowledgeRecord:
        from datetime import datetime
        return KnowledgeRecord(value["knowledge_id"],KnowledgeType(value["knowledge_type"]),value["content"],KnowledgeSource(value["source"]),datetime.fromisoformat(value["created_at"]),datetime.fromisoformat(value["updated_at"]),value["source_request_id"],value["title"],tuple(value["tags"]),KnowledgeStatus(value["status"]),value["metadata"])
