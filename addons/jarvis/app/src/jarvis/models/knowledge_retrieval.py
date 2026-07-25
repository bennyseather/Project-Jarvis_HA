"""Provider-neutral contracts for deterministic Knowledge retrieval."""
from __future__ import annotations
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from jarvis.models.knowledge import KnowledgeRecord, KnowledgeType

class KnowledgeRetrievalEligibility(str, Enum): ELIGIBLE="eligible"; INELIGIBLE="ineligible"
@dataclass(frozen=True, slots=True)
class KnowledgeRetrievalQuery:
    query_text: str = ""; requested_knowledge_types: frozenset[KnowledgeType] = field(default_factory=frozenset)
    requested_tags: tuple[str, ...] = (); maximum_results: int = 5; metadata: Mapping[str, object] = field(default_factory=dict)
    def __post_init__(self) -> None:
        if not 0 <= self.maximum_results <= 10: raise ValueError("maximum_results must be between 0 and 10.")
@dataclass(frozen=True, slots=True)
class KnowledgeRetrievalPolicyResult: eligibility: KnowledgeRetrievalEligibility; reason_code: str
@dataclass(frozen=True, slots=True)
class KnowledgeMatch: record: KnowledgeRecord; total_score: float; score_breakdown: Mapping[str,float]; matched_reasons: tuple[str,...]
@dataclass(frozen=True, slots=True)
class KnowledgeRetrievalResult:
    matches: tuple[KnowledgeMatch,...]; eligible_records_considered: int; records_excluded_by_policy: int
    query_metadata: Mapping[str, object] = field(default_factory=dict)
