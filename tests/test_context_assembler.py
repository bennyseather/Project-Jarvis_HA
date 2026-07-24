"""Unit tests for context assembly."""

import unittest
from dataclasses import replace
from datetime import datetime

from jarvis.context.context_assembler import ContextAssembler
from jarvis.context.providers import (
    EmptyContextProvider,
    MemoryContextProvider,
    StaticContextProvider,
)
from jarvis.models.context import ContextPackage, MemoryContext, MemoryContextMatch
from jarvis.models.memory import (
    MemoryConsentLevel,
    MemoryRecord,
    MemorySource,
    MemoryStatus,
    MemoryType,
)
from jarvis.models.memory_retrieval import MemoryMatch, MemoryRetrievalQuery, MemoryRetrievalResult
from jarvis.models.request import Request
from jarvis.models.request_context import RequestContext


class RecordingRetriever:
    """Return a controlled retrieval result while recording its query."""

    def __init__(self, result: MemoryRetrievalResult) -> None:
        self.result = result
        self.query: MemoryRetrievalQuery | None = None

    def retrieve(self, query: MemoryRetrievalQuery) -> MemoryRetrievalResult:
        self.query = query
        return self.result


class FailingRetriever:
    """Model an unavailable memory provider."""

    def retrieve(self, query: MemoryRetrievalQuery) -> MemoryRetrievalResult:
        raise RuntimeError("memory provider unavailable")


class ContextAssemblerTests(unittest.TestCase):
    """Verify deterministic assembly of registered provider output."""

    def test_populates_request_context_with_an_empty_package(self) -> None:
        request_context = RequestContext(Request("Hello, Jarvis."))
        assembler = ContextAssembler([EmptyContextProvider()])

        package = assembler.assemble(request_context)

        self.assertIs(request_context.context_package, package)
        self.assertIsNone(package.conversation)
        self.assertIsNone(package.memory)
        self.assertIsNone(package.home_assistant)
        self.assertIsNone(package.knowledge)
        self.assertIsNone(package.time)
        self.assertIsNone(package.metadata)

    def test_merges_providers_in_registration_order(self) -> None:
        first_provider = StaticContextProvider(
            ContextPackage(
                knowledge={"room": "kitchen"},
                metadata={"source": "first"},
            )
        )
        second_provider = StaticContextProvider(
            ContextPackage(
                knowledge={"room": "living room", "floor": "ground"},
                time=datetime(2026, 7, 24, 12, 0),
                metadata={"source": "second", "version": 1},
            )
        )
        assembler = ContextAssembler([first_provider])
        assembler.register(second_provider)

        package = assembler.assemble(RequestContext(Request("Where am I?")))

        self.assertEqual(
            package.knowledge,
            {"room": "living room", "floor": "ground"},
        )
        self.assertEqual(package.metadata, {"source": "second", "version": 1})
        self.assertEqual(package.time, datetime(2026, 7, 24, 12, 0))

    def test_memory_provider_adds_a_typed_bounded_context(self) -> None:
        record = self._memory_record()
        retriever = RecordingRetriever(
            MemoryRetrievalResult(
                matches=(
                    MemoryMatch(
                        record=record,
                        total_score=7.25,
                        score_breakdown={},
                        matched_reasons=(),
                    ),
                ),
                eligible_records_considered=1,
                records_excluded_by_policy=0,
            )
        )
        request_context = RequestContext(Request("Where is the project plan?"), "request-7")

        package = ContextAssembler([MemoryContextProvider(retriever)]).assemble(request_context)

        self.assertEqual(
            package.memory,
            MemoryContext(
                matches=(
                    MemoryContextMatch(
                        content="The project plan is in the office.",
                        memory_type=MemoryType.PROJECT,
                        tags=("jarvis",),
                        source=MemorySource.EXPLICIT_USER_REQUEST,
                        retrieval_score=7.25,
                    ),
                ),
                result_limit=5,
            ),
        )
        self.assertEqual(retriever.query.query_text, "Where is the project plan?")
        self.assertEqual(retriever.query.source_request_id, "request-7")
        self.assertEqual(retriever.query.maximum_results, 5)
        self.assertFalse(retriever.query.include_sensitive)

    def test_memory_provider_returns_empty_typed_context_for_no_matches(self) -> None:
        retriever = RecordingRetriever(
            MemoryRetrievalResult((), eligible_records_considered=0, records_excluded_by_policy=2)
        )

        package = MemoryContextProvider(retriever).assemble(RequestContext(Request("Hello")))

        self.assertEqual(package.memory, MemoryContext(matches=(), result_limit=5))

    def test_memory_provider_preserves_retriever_order_and_bounds_requested_limit(self) -> None:
        first = self._memory_record(memory_id="second")
        second = replace(first, memory_id="first", content="Second result")
        retriever = RecordingRetriever(
            MemoryRetrievalResult(
                matches=(
                    MemoryMatch(first, 2.0, {}, ()),
                    MemoryMatch(second, 1.0, {}, ()),
                ),
                eligible_records_considered=2,
                records_excluded_by_policy=0,
            )
        )

        package = MemoryContextProvider(retriever, result_limit=10).assemble(
            RequestContext(Request("Project"))
        )

        self.assertEqual([match.content for match in package.memory.matches], [
            "The project plan is in the office.",
            "Second result",
        ])
        self.assertEqual(retriever.query.maximum_results, 10)
        with self.assertRaises(ValueError):
            MemoryContextProvider(retriever, result_limit=11)
        with self.assertRaises(ValueError):
            MemoryContextProvider(retriever, result_limit=-1)

    def test_memory_provider_defensively_limits_an_overfull_retrieval_result(self) -> None:
        first = self._memory_record(memory_id="memory-a")
        second = replace(first, memory_id="memory-b", content="Second result")
        retriever = RecordingRetriever(
            MemoryRetrievalResult(
                matches=(MemoryMatch(first, 2.0, {}, ()), MemoryMatch(second, 1.0, {}, ())),
                eligible_records_considered=2,
                records_excluded_by_policy=0,
            )
        )

        package = MemoryContextProvider(retriever, result_limit=1).assemble(
            RequestContext(Request("Project"))
        )

        self.assertEqual([match.content for match in package.memory.matches], [
            "The project plan is in the office.",
        ])

    def test_memory_retriever_failure_fails_context_assembly(self) -> None:
        request_context = RequestContext(Request("Project"))

        with self.assertRaisesRegex(RuntimeError, "memory provider unavailable"):
            ContextAssembler([MemoryContextProvider(FailingRetriever())]).assemble(request_context)

        self.assertEqual(request_context.state.value, "failed")

    @staticmethod
    def _memory_record(*, memory_id: str = "memory-1") -> MemoryRecord:
        timestamp = datetime(2026, 7, 24, 12, 0)
        return MemoryRecord(
            memory_id=memory_id,
            memory_type=MemoryType.PROJECT,
            content="The project plan is in the office.",
            source=MemorySource.EXPLICIT_USER_REQUEST,
            consent_level=MemoryConsentLevel.EXPLICIT,
            created_at=timestamp,
            updated_at=timestamp,
            tags=("jarvis",),
            status=MemoryStatus.ACTIVE,
        )
