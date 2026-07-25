"""Provider-neutral storage contract for Jarvis memory."""

from __future__ import annotations

from typing import Protocol

from jarvis.models.memory import MemoryRecord


class DuplicateMemoryError(Exception):
    """Raised when creating a record with an existing memory identifier."""


class MemoryNotFoundError(Exception):
    """Raised when a requested memory record does not exist."""


class InvalidMemoryOperationError(Exception):
    """Raised when a record cannot be stored safely."""


class MemoryStore(Protocol):
    """Persistence mechanics for memory records, independent of policy."""

    def create(self, record: MemoryRecord) -> MemoryRecord:
        """Persist a new record or raise DuplicateMemoryError."""

    def get(self, memory_id: str) -> MemoryRecord:
        """Return one record or raise MemoryNotFoundError."""

    def list_records(self) -> tuple[MemoryRecord, ...]:
        """Return all records in the store's documented stable order."""

    def update(self, record: MemoryRecord) -> MemoryRecord:
        """Replace an existing record or raise MemoryNotFoundError."""

    def delete(self, memory_id: str) -> None:
        """Hard-delete a record or raise MemoryNotFoundError."""

    def clear(self) -> None:
        """Hard-delete every record held by this store."""

    def exists(self, memory_id: str) -> bool:
        """Return whether a record currently exists."""
