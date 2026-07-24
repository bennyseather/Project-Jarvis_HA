"""Deterministic baseline ranking for policy-eligible memory records."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Protocol

from jarvis.models.memory import MemoryRecord
from jarvis.models.memory_retrieval import MemoryMatch, MemoryRetrievalQuery


class MemoryRanker(Protocol):
    """Ranks policy-eligible records for one retrieval query."""

    def rank(
        self,
        query: MemoryRetrievalQuery,
        records: Iterable[MemoryRecord],
    ) -> tuple[MemoryMatch, ...]:
        """Return deterministic matches in descending score order."""


class DeterministicMemoryRanker:
    """Rank records with documented structured signals and no semantic search."""

    _RECENCY_DAYS = 365.0

    def rank(
        self,
        query: MemoryRetrievalQuery,
        records: Iterable[MemoryRecord],
    ) -> tuple[MemoryMatch, ...]:
        """Score records and resolve ties with ascending memory identifiers."""

        matches = tuple(self._match(query, record) for record in records)
        return tuple(sorted(matches, key=lambda match: (-match.total_score, match.record.memory_id)))

    def _match(self, query: MemoryRetrievalQuery, record: MemoryRecord) -> MemoryMatch:
        normalized_query = self._normalize(query.query_text)
        normalized_content = self._normalize(record.content)
        query_tokens = self._tokens(normalized_query)
        content_tokens = self._tokens(normalized_content)
        requested_tags = {self._normalize(tag) for tag in query.requested_tags}
        record_tags = {self._normalize(tag) for tag in record.tags}

        exact_text = 5.0 if normalized_query and normalized_query == normalized_content else 0.0
        token_overlap = self._overlap_score(query_tokens, content_tokens, 4.0)
        tag_overlap = self._overlap_score(requested_tags, record_tags, 2.0)
        importance = record.importance if record.importance is not None else 0.5
        confidence = record.confidence if record.confidence is not None else 0.5
        recency = self._recency_score(record.updated_at, query.evaluation_time)
        breakdown = {
            "exact_text": exact_text,
            "token_overlap": token_overlap,
            "tag_overlap": tag_overlap,
            "importance": importance,
            "confidence": confidence,
            "recency": recency,
        }
        reasons = tuple(name for name, score in breakdown.items() if score > 0.0)

        return MemoryMatch(
            record=record,
            total_score=sum(breakdown.values()),
            score_breakdown=breakdown,
            matched_reasons=reasons,
        )

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join(value.casefold().split())

    @classmethod
    def _tokens(cls, normalized_value: str) -> set[str]:
        return set(normalized_value.split()) if normalized_value else set()

    @staticmethod
    def _overlap_score(query_values: set[str], record_values: set[str], maximum: float) -> float:
        if not query_values:
            return 0.0
        overlap_ratio = len(query_values & record_values) / len(query_values)
        return max(0.0, min(1.0, overlap_ratio)) * maximum

    def _recency_score(self, updated_at: datetime, evaluation_time: datetime | None) -> float:
        if evaluation_time is None:
            raise ValueError("evaluation_time is required for deterministic ranking.")

        age_in_days = (evaluation_time - updated_at).total_seconds() / 86_400.0
        if age_in_days <= 0.0:
            return 1.0
        if age_in_days >= self._RECENCY_DAYS:
            return 0.0
        return max(0.0, min(1.0, 1.0 - age_in_days / self._RECENCY_DAYS))
