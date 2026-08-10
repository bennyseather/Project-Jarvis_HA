"""Deterministic in-memory reference implementation of KnowledgeStore."""

from __future__ import annotations

from copy import deepcopy

from jarvis.knowledge.store import DuplicateKnowledgeError, InvalidKnowledgeOperationError, KnowledgeNotFoundError
from jarvis.models.knowledge import KnowledgeRecord, KnowledgeSource, KnowledgeStatus, KnowledgeType


class InMemoryKnowledgeStore:
    """Process-local storage with no policy, ingestion, or retrieval behavior."""

    def __init__(self) -> None:
        self._records: dict[str, KnowledgeRecord] = {}

    def create(self, record: KnowledgeRecord) -> KnowledgeRecord:
        self._validate(record)
        if record.knowledge_id in self._records:
            raise DuplicateKnowledgeError(f"Knowledge already exists: {record.knowledge_id}")
        self._records[record.knowledge_id] = self._copy(record)
        return self._copy(self._records[record.knowledge_id])

    def get(self, knowledge_id: str) -> KnowledgeRecord:
        try:
            return self._copy(self._records[knowledge_id])
        except KeyError as error:
            raise KnowledgeNotFoundError(f"Knowledge not found: {knowledge_id}") from error

    def list_records(self) -> tuple[KnowledgeRecord, ...]:
        return tuple(self._copy(self._records[key]) for key in sorted(self._records))

    def update(self, record: KnowledgeRecord) -> KnowledgeRecord:
        self._validate(record)
        if record.knowledge_id not in self._records:
            raise KnowledgeNotFoundError(f"Knowledge not found: {record.knowledge_id}")
        self._records[record.knowledge_id] = self._copy(record)
        return self._copy(self._records[record.knowledge_id])

    def delete(self, knowledge_id: str) -> None:
        try:
            del self._records[knowledge_id]
        except KeyError as error:
            raise KnowledgeNotFoundError(f"Knowledge not found: {knowledge_id}") from error

    def clear(self) -> None:
        self._records.clear()

    def exists(self, knowledge_id: str) -> bool:
        return knowledge_id in self._records

    @staticmethod
    def _copy(record: KnowledgeRecord) -> KnowledgeRecord:
        return deepcopy(record)

    @staticmethod
    def _validate(record: KnowledgeRecord) -> None:
        if not isinstance(record, KnowledgeRecord):
            raise InvalidKnowledgeOperationError("A KnowledgeRecord is required.")
        if not record.knowledge_id.strip() or not record.content.strip():
            raise InvalidKnowledgeOperationError("knowledge_id and content must not be empty.")
        if not isinstance(record.knowledge_type, KnowledgeType):
            raise InvalidKnowledgeOperationError("knowledge_type must be a KnowledgeType.")
        if not isinstance(record.source, KnowledgeSource):
            raise InvalidKnowledgeOperationError("source must be a KnowledgeSource.")
        if not isinstance(record.status, KnowledgeStatus):
            raise InvalidKnowledgeOperationError("status must be a KnowledgeStatus.")
        if record.title is not None and not isinstance(record.title, str):
            raise InvalidKnowledgeOperationError("title must be a string or None.")
        if not isinstance(record.tags, tuple) or not all(isinstance(tag, str) for tag in record.tags):
            raise InvalidKnowledgeOperationError("tags must be a tuple of strings.")
