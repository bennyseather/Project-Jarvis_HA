"""Unit tests for policy-controlled deterministic memory retrieval."""

import unittest
from datetime import datetime, timedelta, timezone

from jarvis.memory.in_memory_store import InMemoryMemoryStore
from jarvis.memory.policy import ExplicitMemoryPolicy
from jarvis.memory.ranker import DeterministicMemoryRanker
from jarvis.memory.retriever import PolicyControlledMemoryRetriever
from jarvis.models.memory import (
    MemoryConsentLevel,
    MemoryRecord,
    MemorySource,
    MemoryStatus,
    MemoryType,
)
from jarvis.models.memory_retrieval import MemoryRetrievalQuery


EVALUATION_TIME = datetime(2026, 7, 24, 12, 0, tzinfo=timezone.utc)


class RecordingRanker:
    """Wrap the baseline ranker while recording received memory identifiers."""

    def __init__(self) -> None:
        self.received_ids: tuple[str, ...] = ()
        self._ranker = DeterministicMemoryRanker()

    def rank(self, query: MemoryRetrievalQuery, records):
        self.received_ids = tuple(record.memory_id for record in records)
        return self._ranker.rank(query, records)


class MemoryRetrieverTests(unittest.TestCase):
    """Verify eligibility, filtering, ranking, and safety boundaries."""

    def setUp(self) -> None:
        self.store = InMemoryMemoryStore()
        self.retriever = self._retriever()

    def test_retrieves_active_memory(self) -> None:
        self.store.create(self._record("memory-1", "The kitchen is downstairs."))

        result = self.retriever.retrieve(self._query())

        self.assertEqual([match.record.memory_id for match in result.matches], ["memory-1"])
        self.assertEqual(result.eligible_records_considered, 1)
        self.assertEqual(result.records_excluded_by_policy, 0)

    def test_excludes_non_active_statuses_before_ranking(self) -> None:
        for status in (
            MemoryStatus.SUPERSEDED,
            MemoryStatus.EXPIRED,
            MemoryStatus.PENDING_CONFIRMATION,
            MemoryStatus.REJECTED,
        ):
            self.store.create(self._record(status.value, "Excluded", status=status))

        result = self.retriever.retrieve(self._query())

        self.assertEqual(result.matches, ())
        self.assertEqual(result.records_excluded_by_policy, 4)

    def test_excludes_expiry_at_or_before_evaluation_time(self) -> None:
        self.store.create(
            self._record("boundary", "Expired", expires_at=EVALUATION_TIME)
        )
        self.store.create(
            self._record("future", "Available", expires_at=EVALUATION_TIME + timedelta(seconds=1))
        )

        result = self.retriever.retrieve(self._query())

        self.assertEqual([match.record.memory_id for match in result.matches], ["future"])
        self.assertEqual(result.records_excluded_by_policy, 1)

    def test_excludes_sensitive_records_by_default_and_allows_policy_approved_request(self) -> None:
        self.store.create(
            self._record(
                "sensitive",
                "Sensitive fact",
                consent_level=MemoryConsentLevel.SENSITIVE_CONFIRMED,
            )
        )

        default_result = self.retriever.retrieve(self._query())
        requested_result = self.retriever.retrieve(self._query(include_sensitive=True))

        self.assertEqual(default_result.matches, ())
        self.assertEqual([match.record.memory_id for match in requested_result.matches], ["sensitive"])

    def test_sensitive_request_does_not_bypass_other_policy_conditions(self) -> None:
        self.store.create(
            self._record(
                "expired-sensitive",
                "Sensitive fact",
                consent_level=MemoryConsentLevel.SENSITIVE_CONFIRMED,
                expires_at=EVALUATION_TIME,
            )
        )

        result = self.retriever.retrieve(self._query(include_sensitive=True))

        self.assertEqual(result.matches, ())

    def test_filters_by_requested_memory_types_and_tags_with_match_any(self) -> None:
        self.store.create(self._record("fact", "Kitchen", tags=("home",), memory_type=MemoryType.FACT))
        self.store.create(self._record("project", "Jarvis", tags=("code",), memory_type=MemoryType.PROJECT))
        self.store.create(self._record("preference", "Metric", tags=("units",), memory_type=MemoryType.PREFERENCE))

        result = self.retriever.retrieve(
            self._query(
                requested_memory_types=frozenset({MemoryType.FACT, MemoryType.PROJECT}),
                requested_tags=("CODE", "home"),
            )
        )

        self.assertEqual(
            {match.record.memory_id for match in result.matches},
            {"fact", "project"},
        )

    def test_applies_minimum_importance_and_confidence_filters(self) -> None:
        self.store.create(self._record("qualified", "Qualified", importance=0.8, confidence=0.9))
        self.store.create(self._record("missing", "Missing"))
        self.store.create(self._record("low", "Low", importance=0.4, confidence=0.9))

        result = self.retriever.retrieve(
            self._query(minimum_importance=0.5, minimum_confidence=0.8)
        )

        self.assertEqual([match.record.memory_id for match in result.matches], ["qualified"])

    def test_zero_maximum_results_skips_ranking(self) -> None:
        self.store.create(self._record("memory-1", "Content"))
        ranker = RecordingRanker()
        retriever = self._retriever(ranker=ranker)

        result = retriever.retrieve(self._query(maximum_results=0))

        self.assertEqual(result.matches, ())
        self.assertEqual(ranker.received_ids, ())

    def test_rejects_invalid_query_limits_and_thresholds(self) -> None:
        with self.assertRaises(ValueError):
            self._query(maximum_results=-1)
        with self.assertRaises(ValueError):
            self._query(minimum_importance=1.1)
        with self.assertRaises(ValueError):
            self._query(minimum_confidence=-0.1)

    def test_exact_normalized_match_and_token_overlap_both_contribute(self) -> None:
        self.store.create(self._record("memory-1", "  HELLO   World  "))

        match = self.retriever.retrieve(self._query(query_text="hello world")).matches[0]

        self.assertEqual(match.score_breakdown["exact_text"], 5.0)
        self.assertEqual(match.score_breakdown["token_overlap"], 4.0)
        self.assertEqual(match.total_score, sum(match.score_breakdown.values()))

    def test_scores_token_overlap_and_tag_overlap(self) -> None:
        self.store.create(self._record("memory-1", "Kitchen ceiling lights", tags=("Lighting", "home")))

        match = self.retriever.retrieve(
            self._query(query_text="kitchen fan", requested_tags=("lighting", "other"))
        ).matches[0]

        self.assertEqual(match.score_breakdown["token_overlap"], 2.0)
        self.assertEqual(match.score_breakdown["tag_overlap"], 1.0)
        self.assertNotIn("type_match", match.score_breakdown)

    def test_uses_neutral_defaults_and_documented_recency_boundaries(self) -> None:
        self.store.create(self._record("now", "Now", updated_at=EVALUATION_TIME))
        self.store.create(
            self._record("middle", "Middle", updated_at=EVALUATION_TIME - timedelta(days=182.5))
        )
        self.store.create(
            self._record("old", "Old", updated_at=EVALUATION_TIME - timedelta(days=365))
        )
        self.store.create(
            self._record("future", "Future", updated_at=EVALUATION_TIME + timedelta(days=1))
        )

        matches = {match.record.memory_id: match for match in self.retriever.retrieve(self._query()).matches}

        self.assertEqual(matches["now"].score_breakdown["importance"], 0.5)
        self.assertEqual(matches["now"].score_breakdown["confidence"], 0.5)
        self.assertEqual(matches["now"].score_breakdown["recency"], 1.0)
        self.assertEqual(matches["middle"].score_breakdown["recency"], 0.5)
        self.assertEqual(matches["old"].score_breakdown["recency"], 0.0)
        self.assertEqual(matches["future"].score_breakdown["recency"], 1.0)

    def test_supports_empty_query_and_stable_memory_id_tie_breaking(self) -> None:
        self.store.create(self._record("memory-b", "Same", updated_at=EVALUATION_TIME))
        self.store.create(self._record("memory-a", "Same", updated_at=EVALUATION_TIME))

        matches = self.retriever.retrieve(self._query(query_text="")).matches

        self.assertEqual([match.record.memory_id for match in matches], ["memory-a", "memory-b"])
        self.assertEqual(matches[0].score_breakdown["exact_text"], 0.0)
        self.assertEqual(matches[0].score_breakdown["token_overlap"], 0.0)

    def test_applies_policy_and_query_filters_before_ranking_and_result_limit(self) -> None:
        self.store.create(self._record("eligible", "Kitchen", memory_type=MemoryType.FACT))
        self.store.create(self._record("filtered", "Kitchen", memory_type=MemoryType.PROJECT))
        self.store.create(self._record("ineligible", "Kitchen", status=MemoryStatus.REJECTED))
        ranker = RecordingRanker()
        retriever = self._retriever(ranker=ranker)

        result = retriever.retrieve(
            self._query(
                requested_memory_types=frozenset({MemoryType.FACT}),
                maximum_results=1,
            )
        )

        self.assertEqual(ranker.received_ids, ("eligible",))
        self.assertEqual([match.record.memory_id for match in result.matches], ["eligible"])

    def test_returned_matches_cannot_mutate_store_contents(self) -> None:
        self.store.create(self._record("memory-1", "Content", metadata={"nested": {"value": 1}}))

        match = self.retriever.retrieve(self._query()).matches[0]
        match.record.metadata["nested"]["value"] = 2

        self.assertEqual(self.store.get("memory-1").metadata["nested"]["value"], 1)

    def _retriever(self, ranker=None) -> PolicyControlledMemoryRetriever:
        return PolicyControlledMemoryRetriever(
            store=self.store,
            policy=ExplicitMemoryPolicy(),
            ranker=DeterministicMemoryRanker() if ranker is None else ranker,
            timestamp_factory=lambda: EVALUATION_TIME,
        )

    @staticmethod
    def _query(**kwargs: object) -> MemoryRetrievalQuery:
        return MemoryRetrievalQuery(evaluation_time=EVALUATION_TIME, **kwargs)

    @staticmethod
    def _record(
        memory_id: str,
        content: str,
        *,
        memory_type: MemoryType = MemoryType.FACT,
        consent_level: MemoryConsentLevel = MemoryConsentLevel.EXPLICIT,
        status: MemoryStatus = MemoryStatus.ACTIVE,
        expires_at: datetime | None = None,
        importance: float | None = None,
        confidence: float | None = None,
        tags: tuple[str, ...] = (),
        updated_at: datetime = EVALUATION_TIME,
        metadata: dict[str, object] | None = None,
    ) -> MemoryRecord:
        return MemoryRecord(
            memory_id=memory_id,
            memory_type=memory_type,
            content=content,
            source=MemorySource.EXPLICIT_USER_REQUEST,
            consent_level=consent_level,
            created_at=EVALUATION_TIME,
            updated_at=updated_at,
            expires_at=expires_at,
            importance=importance,
            confidence=confidence,
            tags=tags,
            status=status,
            metadata={} if metadata is None else metadata,
        )
