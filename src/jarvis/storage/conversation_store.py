"""Durable SQLite short-term conversation storage with strict retention."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jarvis.models.conversation_memory import StoredConversationMessage


class SQLiteConversationStore:
    """Keep the newest conversations within both count and age bounds."""

    def __init__(
        self,
        database_path: str | Path,
        *,
        maximum_conversations: int = 20,
        retention_days: int = 3,
        maximum_messages: int = 100,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not 1 <= maximum_conversations <= 100:
            raise ValueError("maximum_conversations must be between 1 and 100")
        if not 1 <= retention_days <= 30:
            raise ValueError("retention_days must be between 1 and 30")
        if not 2 <= maximum_messages <= 500:
            raise ValueError("maximum_messages must be between 2 and 500")
        self._maximum_conversations = maximum_conversations
        self._retention_days = retention_days
        self._maximum_messages = maximum_messages
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        path = Path(database_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(path)
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._migrate_schema()
        self.prune()

    def _migrate_schema(self) -> None:
        """Apply conversation and reflective-learning schema migrations."""
        with self._connection:
            self._connection.execute(
                "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)"
            )
            if self._connection.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0] == 0:
                self._connection.execute("INSERT INTO schema_version VALUES (1)")
            version = int(self._connection.execute(
                "SELECT version FROM schema_version LIMIT 1"
            ).fetchone()[0])
            if version > 4:
                raise RuntimeError(f"Unsupported database schema version: {version}")
            self._connection.execute(
                """CREATE TABLE IF NOT EXISTS conversations (
                    conversation_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )"""
            )
            self._connection.execute(
                """CREATE TABLE IF NOT EXISTS conversation_messages (
                    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL REFERENCES conversations(conversation_id)
                        ON DELETE CASCADE,
                    role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )"""
            )
            self._connection.execute(
                "CREATE INDEX IF NOT EXISTS conversation_messages_session "
                "ON conversation_messages(conversation_id, message_id)"
            )
            self._connection.execute(
                """CREATE TABLE IF NOT EXISTS repeated_context_occurrences (
                    candidate_key TEXT NOT NULL,
                    message_id INTEGER NOT NULL REFERENCES conversation_messages(message_id)
                        ON DELETE CASCADE,
                    canonical_content TEXT NOT NULL,
                    category TEXT NOT NULL,
                    is_sensitive INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(candidate_key, message_id)
                )"""
            )
            self._connection.execute(
                """CREATE TABLE IF NOT EXISTS repeated_context_promotions (
                    candidate_key TEXT PRIMARY KEY,
                    memory_id TEXT,
                    promoted_at TEXT NOT NULL
                )"""
            )
            self._connection.execute(
                """CREATE TABLE IF NOT EXISTS conversation_learning_preferences (
                    conversation_id TEXT PRIMARY KEY,
                    disabled INTEGER NOT NULL DEFAULT 0
                )"""
            )
            if version < 4:
                self._connection.execute("UPDATE schema_version SET version=4")

    @staticmethod
    def normalize_conversation_id(value: str | None) -> str:
        normalized = "" if value is None else value.strip()
        if not normalized:
            return "local-default"
        return normalized[:200]

    def add_message(self, conversation_id: str | None, role: str, content: str) -> StoredConversationMessage:
        if role not in {"user", "assistant"}:
            raise ValueError("role must be user or assistant")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("content must be non-empty")
        identifier = self.normalize_conversation_id(conversation_id)
        now = self._as_utc(self._clock()).isoformat()
        with self._connection:
            self._connection.execute(
                "INSERT INTO conversations(conversation_id, created_at, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(conversation_id) DO UPDATE SET updated_at=excluded.updated_at",
                (identifier, now, now),
            )
            cursor = self._connection.execute(
                "INSERT INTO conversation_messages(conversation_id, role, content, created_at) "
                "VALUES (?, ?, ?, ?)",
                (identifier, role, content.strip(), now),
            )
            self._connection.execute(
                """DELETE FROM conversation_messages
                   WHERE conversation_id = ? AND message_id NOT IN (
                       SELECT message_id FROM conversation_messages
                       WHERE conversation_id = ? ORDER BY message_id DESC LIMIT ?
                   )""",
                (identifier, identifier, self._maximum_messages),
            )
        self.prune()
        return StoredConversationMessage(
            int(cursor.lastrowid), identifier, role, content.strip(), datetime.fromisoformat(now)
        )

    def history(self, conversation_id: str | None, limit: int = 20) -> tuple[StoredConversationMessage, ...]:
        if not 1 <= limit <= self._maximum_messages:
            raise ValueError("history limit is outside the configured bound")
        identifier = self.normalize_conversation_id(conversation_id)
        rows = self._connection.execute(
            """SELECT message_id, conversation_id, role, content, created_at
               FROM (
                   SELECT * FROM conversation_messages WHERE conversation_id = ?
                   ORDER BY message_id DESC LIMIT ?
               ) ORDER BY message_id""",
            (identifier, limit),
        ).fetchall()
        return tuple(self._decode(row) for row in rows)

    def recent_user_messages(self, limit: int = 200) -> tuple[StoredConversationMessage, ...]:
        rows = self._connection.execute(
            """SELECT message_id, conversation_id, role, content, created_at
               FROM conversation_messages WHERE role='user'
               ORDER BY message_id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return tuple(self._decode(row) for row in reversed(rows))

    def list_conversations(self) -> tuple[str, ...]:
        return tuple(
            row[0] for row in self._connection.execute(
                "SELECT conversation_id FROM conversations ORDER BY updated_at DESC"
            )
        )

    def clear(self, conversation_id: str | None = None) -> int:
        with self._connection:
            if conversation_id is None:
                count = self._connection.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
                self._connection.execute("DELETE FROM conversations")
            else:
                identifier = self.normalize_conversation_id(conversation_id)
                cursor = self._connection.execute(
                    "DELETE FROM conversations WHERE conversation_id=?", (identifier,)
                )
                count = cursor.rowcount
        return int(count)

    def record_candidate(
        self,
        message_id: int,
        key: str,
        content: str,
        category: str,
        is_sensitive: bool,
    ) -> int:
        normalized_key = " ".join(key.casefold().split())[:240]
        if not normalized_key:
            raise ValueError("candidate key must be non-empty")
        with self._connection:
            self._connection.execute(
                """INSERT OR IGNORE INTO repeated_context_occurrences
                   (candidate_key, message_id, canonical_content, category, is_sensitive)
                   VALUES (?, ?, ?, ?, ?)""",
                (normalized_key, message_id, content.strip(), category, int(is_sensitive)),
            )
        return int(self._connection.execute(
            "SELECT COUNT(*) FROM repeated_context_occurrences WHERE candidate_key=?",
            (normalized_key,),
        ).fetchone()[0])

    def is_promoted(self, key: str) -> bool:
        normalized_key = " ".join(key.casefold().split())[:240]
        return self._connection.execute(
            "SELECT 1 FROM repeated_context_promotions WHERE candidate_key=?", (normalized_key,)
        ).fetchone() is not None

    def mark_promoted(self, key: str, memory_id: str | None) -> None:
        normalized_key = " ".join(key.casefold().split())[:240]
        with self._connection:
            self._connection.execute(
                "INSERT OR REPLACE INTO repeated_context_promotions VALUES (?, ?, ?)",
                (normalized_key, memory_id, self._as_utc(self._clock()).isoformat()),
            )

    def promoted_memory_id(self, key: str) -> str | None:
        normalized_key = " ".join(key.casefold().split())[:240]
        row = self._connection.execute(
            "SELECT memory_id FROM repeated_context_promotions WHERE candidate_key=?",
            (normalized_key,),
        ).fetchone()
        return None if row is None else row[0]

    def candidate_sources(self, key: str) -> tuple[str, ...]:
        normalized_key = " ".join(key.casefold().split())[:240]
        rows = self._connection.execute(
            """SELECT DISTINCT m.conversation_id
               FROM repeated_context_occurrences AS o
               JOIN conversation_messages AS m ON m.message_id=o.message_id
               WHERE o.candidate_key=? ORDER BY m.conversation_id""",
            (normalized_key,),
        ).fetchall()
        return tuple(str(row[0]) for row in rows)

    def set_learning_disabled(
        self, conversation_id: str | None, disabled: bool
    ) -> None:
        identifier = self.normalize_conversation_id(conversation_id)
        with self._connection:
            self._connection.execute(
                """INSERT INTO conversation_learning_preferences
                   (conversation_id, disabled) VALUES (?, ?)
                   ON CONFLICT(conversation_id)
                   DO UPDATE SET disabled=excluded.disabled""",
                (identifier, int(disabled)),
            )

    def is_learning_disabled(self, conversation_id: str | None) -> bool:
        identifier = self.normalize_conversation_id(conversation_id)
        row = self._connection.execute(
            "SELECT disabled FROM conversation_learning_preferences "
            "WHERE conversation_id=?",
            (identifier,),
        ).fetchone()
        return bool(row and row[0])

    def prune(self) -> None:
        cutoff = (self._as_utc(self._clock()) - timedelta(days=self._retention_days)).isoformat()
        with self._connection:
            self._connection.execute("DELETE FROM conversations WHERE updated_at < ?", (cutoff,))
            self._connection.execute(
                """DELETE FROM conversations WHERE conversation_id NOT IN (
                       SELECT conversation_id FROM conversations
                       ORDER BY updated_at DESC, conversation_id ASC LIMIT ?
                   )""",
                (self._maximum_conversations,),
            )

    def close(self) -> None:
        self._connection.close()

    @staticmethod
    def _decode(row) -> StoredConversationMessage:
        return StoredConversationMessage(
            int(row[0]), str(row[1]), str(row[2]), str(row[3]), datetime.fromisoformat(row[4])
        )

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
