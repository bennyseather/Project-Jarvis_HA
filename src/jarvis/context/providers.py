"""Initial non-integrating context providers."""

from __future__ import annotations

from jarvis.memory.retriever import MemoryRetriever
from jarvis.knowledge.retriever import KnowledgeRetriever
from jarvis.models.context import ContextPackage
from jarvis.models.context import MemoryContext, MemoryContextMatch
from jarvis.models.context import KnowledgeContext, KnowledgeContextMatch
from jarvis.models.knowledge_retrieval import KnowledgeRetrievalQuery
from jarvis.models.memory_retrieval import MemoryRetrievalQuery
from jarvis.models.request_context import RequestContext


class EmptyContextProvider:
    """Placeholder provider used when no context source is available."""

    def assemble(self, request_context: RequestContext) -> ContextPackage:
        """Return an empty package without consulting external systems."""

        return ContextPackage()


class StaticContextProvider:
    """Provide pre-supplied context for controlled local use and testing."""

    def __init__(self, context: ContextPackage) -> None:
        self._context = context

    def assemble(self, request_context: RequestContext) -> ContextPackage:
        """Return the provider's fixed partial package."""

        return self._context


class MemoryContextProvider:
    """Provide bounded, retrieval-safe memory through a MemoryRetriever."""

    _DEFAULT_RESULT_LIMIT = 5
    _MAXIMUM_RESULT_LIMIT = 10

    def __init__(
        self,
        retriever: MemoryRetriever,
        *,
        result_limit: int = _DEFAULT_RESULT_LIMIT,
    ) -> None:
        if not 0 <= result_limit <= self._MAXIMUM_RESULT_LIMIT:
            raise ValueError(
                f"result_limit must be between 0 and {self._MAXIMUM_RESULT_LIMIT}."
            )
        self._retriever = retriever
        self._result_limit = result_limit

    def assemble(self, request_context: RequestContext) -> ContextPackage:
        """Retrieve approved memory without exposing storage-specific fields."""

        result = self._retriever.retrieve(
            MemoryRetrievalQuery(
                query_text=request_context.request.content,
                source_request_id=request_context.request_id,
                maximum_results=self._result_limit,
                include_sensitive=False,
            )
        )
        matches = tuple(
            MemoryContextMatch(
                content=match.record.content,
                memory_type=match.record.memory_type,
                tags=match.record.tags,
                source=match.record.source,
                retrieval_score=match.total_score,
            )
            for match in result.matches[: self._result_limit]
        )
        return ContextPackage(memory=MemoryContext(matches, self._result_limit))

class KnowledgeContextProvider:
    _DEFAULT_RESULT_LIMIT = 5; _MAXIMUM_RESULT_LIMIT = 10
    def __init__(self, retriever: KnowledgeRetriever, *, result_limit: int = _DEFAULT_RESULT_LIMIT) -> None:
        if not 0 <= result_limit <= self._MAXIMUM_RESULT_LIMIT: raise ValueError("result_limit must be between 0 and 10.")
        self._retriever,self._result_limit=retriever,result_limit
    def assemble(self, request_context: RequestContext) -> ContextPackage:
        result=self._retriever.retrieve(KnowledgeRetrievalQuery(query_text=request_context.request.content,maximum_results=self._result_limit))
        matches=tuple(KnowledgeContextMatch(m.record.content,m.record.title,m.record.knowledge_type,m.record.tags,m.record.source,m.total_score) for m in result.matches[:self._result_limit])
        return ContextPackage(knowledge=KnowledgeContext(matches,self._result_limit))
