"""Policy-controlled coordination of memory retrieval and ranking."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from typing import Protocol

from jarvis.memory.policy import MemoryPolicy
from jarvis.memory.ranker import MemoryRanker
from jarvis.memory.store import MemoryStore
from jarvis.models.memory import MemoryRecord
from jarvis.models.memory_retrieval import (
    MemoryRetrievalEligibility,
    MemoryRetrievalQuery,
    MemoryRetrievalResult,
)


class MemoryRetriever(Protocol):
    """Reads, filters, and ranks memory without modifying MemoryStore."""

    def retrieve(self, query: MemoryRetrievalQuery) -> MemoryRetrievalResult:
        """Return deterministic policy-eligible matches for one query."""


class PolicyControlledMemoryRetriever:
    """Apply policy, query filters, and ranking in a fixed order."""

    def __init__(
        self,
        store: MemoryStore,
        policy: MemoryPolicy,
        ranker: MemoryRanker,
        timestamp_factory: Callable[[], datetime],
    ) -> None:
        self._store = store
        self._policy = policy
        self._ranker = ranker
        self._timestamp_factory = timestamp_factory

    def retrieve(self, query: MemoryRetrievalQuery) -> MemoryRetrievalResult:
        """Retrieve, filter, rank, and limit records without writing storage."""

        effective_query = self._with_evaluation_time(query)
        eligible_records: list[MemoryRecord] = []
        excluded_by_policy = 0

        for record in self._store.list_records():
            policy_result = self._policy.evaluate_retrieval(record, effective_query)
            if policy_result.eligibility is MemoryRetrievalEligibility.INELIGIBLE:
                excluded_by_policy += 1
                continue
            eligible_records.append(record)

        query_filtered_records = tuple(
            record for record in eligible_records if self._matches_query(record, effective_query)
        )
        matches = (
            ()
            if effective_query.maximum_results == 0
            else self._ranker.rank(effective_query, query_filtered_records)
        )

        return MemoryRetrievalResult(
            matches=matches[: effective_query.maximum_results],
            eligible_records_considered=len(eligible_records),
            records_excluded_by_policy=excluded_by_policy,
            query_metadata={"evaluation_time": effective_query.evaluation_time},
        )

    def _with_evaluation_time(self, query: MemoryRetrievalQuery) -> MemoryRetrievalQuery:
        if query.evaluation_time is not None:
            return query
        return replace(query, evaluation_time=self._timestamp_factory())

    @staticmethod
    def _matches_query(record: MemoryRecord, query: MemoryRetrievalQuery) -> bool:
        if query.requested_memory_types and record.memory_type not in query.requested_memory_types:
            return False

        requested_tags = {PolicyControlledMemoryRetriever._normalize(tag) for tag in query.requested_tags}
        if requested_tags:
            record_tags = {PolicyControlledMemoryRetriever._normalize(tag) for tag in record.tags}
            if not requested_tags & record_tags:
                return False

        if query.minimum_importance is not None:
            if record.importance is None or record.importance < query.minimum_importance:
                return False
        if query.minimum_confidence is not None:
            if record.confidence is None or record.confidence < query.minimum_confidence:
                return False
        return True

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join(value.casefold().split())
