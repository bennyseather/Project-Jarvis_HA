"""Assembly of contextual information for a request."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Protocol

from jarvis.models.context import ContextPackage
from jarvis.models.request_context import RequestContext
from jarvis.models.request_state import RequestState


class ContextProvider(Protocol):
    """Provides one partial context package for a request."""

    def assemble(self, request_context: RequestContext) -> ContextPackage:
        """Return context information relevant to ``request_context``."""


class ContextAssembler:
    """Collect registered provider output into one deterministic context package."""

    def __init__(self, providers: Iterable[ContextProvider] = ()) -> None:
        self._providers = list(providers)

    def register(self, provider: ContextProvider) -> None:
        """Register a context provider in assembly order."""

        self._providers.append(provider)

    def assemble(self, request_context: RequestContext) -> ContextPackage:
        """Assemble provider output and add it to ``request_context``."""

        try:
            package = ContextPackage()

            for provider in self._providers:
                package = self._merge(package, provider.assemble(request_context))
        except Exception:
            request_context.state = RequestState.FAILED
            raise

        request_context.context_package = package
        request_context.state = RequestState.CONTEXT_ASSEMBLED
        return package

    @staticmethod
    def _merge(current: ContextPackage, partial: ContextPackage) -> ContextPackage:
        """Merge a partial package; later providers take precedence for conflicts."""

        return ContextPackage(
            conversation=ContextAssembler._merge_conversation(
                current.conversation,
                partial.conversation,
            ),
            memory=partial.memory if partial.memory is not None else current.memory,
            home_assistant=ContextAssembler._merge_mapping(
                current.home_assistant,
                partial.home_assistant,
            ),
            knowledge=ContextAssembler._merge_mapping(
                current.knowledge,
                partial.knowledge,
            ),
            time=partial.time if partial.time is not None else current.time,
            metadata=ContextAssembler._merge_mapping(current.metadata, partial.metadata),
        )

    @staticmethod
    def _merge_conversation(
        current: tuple[object, ...] | None,
        partial: tuple[object, ...] | None,
    ) -> tuple[object, ...] | None:
        if current is None:
            return partial
        if partial is None:
            return current
        return current + partial

    @staticmethod
    def _merge_mapping(
        current: Mapping[str, object] | None,
        partial: Mapping[str, object] | None,
    ) -> dict[str, object] | None:
        if current is None:
            return dict(partial) if partial is not None else None
        if partial is None:
            return dict(current)
        return {**current, **partial}
