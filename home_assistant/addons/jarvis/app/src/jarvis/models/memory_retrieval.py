"""Provider-neutral contracts for deterministic memory retrieval."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from jarvis.models.memory import MemoryRecord, MemoryType


class MemoryRetrievalEligibility(str, Enum):
    """Policy eligibility outcomes for a stored record."""

    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"


@dataclass(frozen=True, slots=True)
class MemoryRetrievalQuery:
    """A provider-neutral request for policy-controlled memory retrieval."""

    query_text: str = ""
    source_request_id: str | None = None
    requested_memory_types: frozenset[MemoryType] = field(default_factory=frozenset)
    requested_tags: tuple[str, ...] = ()
    maximum_results: int = 10
    minimum_importance: float | None = None
    minimum_confidence: float | None = None
    evaluation_time: datetime | None = None
    include_sensitive: bool = False
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.maximum_results < 0:
            raise ValueError("maximum_results must be non-negative.")
        self._validate_threshold("minimum_importance", self.minimum_importance)
        self._validate_threshold("minimum_confidence", self.minimum_confidence)

    @staticmethod
    def _validate_threshold(name: str, value: float | None) -> None:
        if value is not None and not 0.0 <= value <= 1.0:
            raise ValueError(f"{name} must be between 0.0 and 1.0.")


@dataclass(frozen=True, slots=True)
class MemoryRetrievalPolicyResult:
    """A policy decision about one record's retrieval eligibility."""

    eligibility: MemoryRetrievalEligibility
    reason_code: str


@dataclass(frozen=True, slots=True)
class MemoryMatch:
    """One ranked record and its inspectable deterministic score."""

    record: MemoryRecord
    total_score: float
    score_breakdown: Mapping[str, float]
    matched_reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MemoryRetrievalResult:
    """The ordered outcome of a memory retrieval operation."""

    matches: tuple[MemoryMatch, ...]
    eligible_records_considered: int
    records_excluded_by_policy: int
    query_metadata: Mapping[str, object] = field(default_factory=dict)
