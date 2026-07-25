"""Deterministic in-memory reference implementation of MemoryStore."""

from __future__ import annotations

from copy import deepcopy

from jarvis.memory.store import (
    DuplicateMemoryError,
    InvalidMemoryOperationError,
    MemoryNotFoundError,
)
from jarvis.models.memory import MemoryRecord


class InMemoryMemoryStore:
    """Store records for the current process without policy or ranking logic."""

    def __init__(self) -> None:
        self._records: dict[str, MemoryRecord] = {}

    def create(self, record: MemoryRecord) -> MemoryRecord:
        """Store a new record, rejecting duplicate identifiers."""

        self._validate(record)
        if record.memory_id in self._records:
            raise DuplicateMemoryError(f"Memory already exists: {record.memory_id}")

        self._records[record.memory_id] = self._copy(record)
        return self._copy(self._records[record.memory_id])

    def get(self, memory_id: str) -> MemoryRecord:
        """Return a defensive copy of one stored record."""

        try:
            return self._copy(self._records[memory_id])
        except KeyError as error:
            raise MemoryNotFoundError(f"Memory not found: {memory_id}") from error

    def list_records(self) -> tuple[MemoryRecord, ...]:
        """Return defensive copies ordered by ascending memory identifier."""

        return tuple(
            self._copy(self._records[memory_id])
            for memory_id in sorted(self._records)
        )

    def update(self, record: MemoryRecord) -> MemoryRecord:
        """Replace a stored record without retaining the prior value."""

        self._validate(record)
        if record.memory_id not in self._records:
            raise MemoryNotFoundError(f"Memory not found: {record.memory_id}")

        self._records[record.memory_id] = self._copy(record)
        return self._copy(self._records[record.memory_id])

    def delete(self, memory_id: str) -> None:
        """Hard-delete a record and every reference held by this backend."""

        try:
            del self._records[memory_id]
        except KeyError as error:
            raise MemoryNotFoundError(f"Memory not found: {memory_id}") from error

    def clear(self) -> None:
        """Hard-delete all records held by this backend."""

        self._records.clear()

    def exists(self, memory_id: str) -> bool:
        """Return whether a record identifier is currently stored."""

        return memory_id in self._records

    @staticmethod
    def _copy(record: MemoryRecord) -> MemoryRecord:
        return deepcopy(record)

    @staticmethod
    def _validate(record: MemoryRecord) -> None:
        if not isinstance(record, MemoryRecord):
            raise InvalidMemoryOperationError("A MemoryRecord is required.")
        if not record.memory_id.strip():
            raise InvalidMemoryOperationError("memory_id must not be empty.")
        if not record.content.strip():
            raise InvalidMemoryOperationError("content must not be empty.")
        for field_name, value in (
            ("importance", record.importance),
            ("confidence", record.confidence),
        ):
            if value is not None and not 0.0 <= value <= 1.0:
                raise InvalidMemoryOperationError(
                    f"{field_name} must be between 0.0 and 1.0."
                )
