"""Deterministic normalization of execution outcomes into responses."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from jarvis.models.execution import ExecutionResult, ExecutionStatus
from jarvis.models.request_context import RequestContext
from jarvis.models.request_state import RequestState
from jarvis.models.response import (
    ConfirmationRequest,
    FollowUpAction,
    Response,
    ResponseStatus,
)
from jarvis.response.renderers import ResponseRenderer, StructuredResponseRenderer


class ResponsePipeline:
    """Normalize an execution result through a provider-neutral renderer."""

    def __init__(
        self,
        timestamp_factory: Callable[[], datetime],
        renderer: ResponseRenderer | None = None,
    ) -> None:
        self._timestamp_factory = timestamp_factory
        self._renderer = renderer or StructuredResponseRenderer()

    def process(self, request_context: RequestContext) -> Response:
        """Create, render, and store a response for ``request_context``."""

        try:
            execution_result = request_context.execution_result
            if not isinstance(execution_result, ExecutionResult):
                response = self._missing_execution_response()
            else:
                response = self._response_for(execution_result)

            rendered_response = self._renderer.render(response)
        except Exception:
            request_context.state = RequestState.FAILED
            raise

        request_context.response = rendered_response
        if request_context.state is not RequestState.CANCELLED:
            request_context.state = RequestState.COMPLETED
        return rendered_response

    def _missing_execution_response(self) -> Response:
        return Response(
            status=ResponseStatus.NOT_SUPPORTED,
            summary="not_supported",
            detailed_message="No execution result is available.",
            timestamp=self._timestamp_factory(),
        )

    def _response_for(self, result: ExecutionResult) -> Response:
        status = ResponseStatus(result.status.value)
        follow_up_actions, confirmation_request = self._next_actions(result.status)

        return Response(
            status=status,
            summary=status.value,
            detailed_message=result.message,
            metadata={"execution_status": result.status.value, **result.metadata},
            follow_up_actions=follow_up_actions,
            confirmation_request=confirmation_request,
            timestamp=self._timestamp_factory(),
        )

    @staticmethod
    def _next_actions(
        status: ExecutionStatus,
    ) -> tuple[tuple[FollowUpAction, ...], ConfirmationRequest | None]:
        if status in {ExecutionStatus.FAILED, ExecutionStatus.PARTIAL}:
            return (FollowUpAction("retry_execution"),), None
        if status is ExecutionStatus.NOT_SUPPORTED:
            return (FollowUpAction("select_supported_capability"),), None
        if status is ExecutionStatus.CANCELLED:
            return (), ConfirmationRequest("confirm_execution")
        return (), None
