"""Deterministic execution of declarative plans."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from jarvis.models.execution import (
    ExecutionPlan,
    ExecutionResult,
    ExecutionStatus,
    ExecutionStep,
)
from jarvis.models.request_context import RequestContext
from jarvis.models.request_state import RequestState


class ExecutionStepHandler(Protocol):
    """Executes one generic execution step."""

    def execute(
        self,
        request_context: RequestContext,
        step: ExecutionStep,
    ) -> ExecutionResult:
        """Execute a step and report its structured outcome."""


class ExecutionPipeline:
    """Run plan steps sequentially through registered handlers."""

    def __init__(self, handlers: Mapping[str, ExecutionStepHandler] | None = None) -> None:
        self._handlers = dict(handlers) if handlers is not None else {}

    def execute(
        self,
        request_context: RequestContext,
        plan: ExecutionPlan,
    ) -> ExecutionResult:
        """Execute a plan in order and add its result to ``request_context``."""

        request_context.state = RequestState.EXECUTING

        try:
            if plan.requires_confirmation:
                return self._store_result(
                    request_context,
                    ExecutionResult(
                        ExecutionStatus.CANCELLED,
                        "Execution requires confirmation.",
                    ),
                )

            if not plan.steps:
                return self._store_result(
                    request_context,
                    ExecutionResult(
                        ExecutionStatus.NOT_SUPPORTED,
                        "No execution steps are available.",
                    ),
                )

            completed_steps = 0

            for step in plan.steps:
                handler = self._handlers.get(step.name)
                if handler is None:
                    return self._store_result(
                        request_context,
                        self._unsupported_result(step, completed_steps),
                    )

                result = handler.execute(request_context, step)
                if result.status is not ExecutionStatus.SUCCESS:
                    return self._store_result(
                        request_context,
                        self._stopped_result(result, completed_steps),
                    )

                completed_steps += 1

            return self._store_result(
                request_context,
                ExecutionResult(
                    ExecutionStatus.SUCCESS,
                    "Execution completed successfully.",
                    metadata={"completed_steps": completed_steps},
                ),
            )
        except Exception:
            request_context.state = RequestState.FAILED
            raise

    @staticmethod
    def _unsupported_result(step: ExecutionStep, completed_steps: int) -> ExecutionResult:
        status = (
            ExecutionStatus.PARTIAL
            if completed_steps
            else ExecutionStatus.NOT_SUPPORTED
        )
        return ExecutionResult(
            status,
            f"No handler is registered for execution step: {step.name}",
            metadata={"completed_steps": completed_steps},
        )

    @staticmethod
    def _stopped_result(
        result: ExecutionResult,
        completed_steps: int,
    ) -> ExecutionResult:
        if not completed_steps:
            return result

        return ExecutionResult(
            ExecutionStatus.PARTIAL,
            result.message,
            metadata={"completed_steps": completed_steps, **result.metadata},
            error=result.error,
        )

    @staticmethod
    def _store_result(
        request_context: RequestContext,
        result: ExecutionResult,
    ) -> ExecutionResult:
        request_context.execution_result = result
        request_context.state = (
            RequestState.CANCELLED
            if result.status is ExecutionStatus.CANCELLED
            else RequestState.COMPLETED
        )
        return result
