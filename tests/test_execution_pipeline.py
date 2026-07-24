"""Unit tests for the execution pipeline."""

import unittest

from jarvis.execution.execution_pipeline import ExecutionPipeline
from jarvis.models.execution import (
    ExecutionPlan,
    ExecutionResult,
    ExecutionStatus,
    ExecutionStep,
)
from jarvis.models.request import Request
from jarvis.models.request_context import RequestContext


class RecordingHandler:
    """A test handler that records the order of executed steps."""

    def __init__(self, executed_steps: list[str], result: ExecutionResult) -> None:
        self._executed_steps = executed_steps
        self._result = result

    def execute(
        self,
        request_context: RequestContext,
        step: ExecutionStep,
    ) -> ExecutionResult:
        self._executed_steps.append(step.name)
        return self._result


class ExecutionPipelineTests(unittest.TestCase):
    """Verify sequential pipeline execution and terminal outcomes."""

    def test_executes_steps_in_order_and_stores_success(self) -> None:
        executed_steps: list[str] = []
        success = ExecutionResult(ExecutionStatus.SUCCESS, "Step completed.")
        pipeline = ExecutionPipeline(
            {
                "first": RecordingHandler(executed_steps, success),
                "second": RecordingHandler(executed_steps, success),
            }
        )
        request_context = RequestContext(Request("Test request"))
        plan = ExecutionPlan(steps=(ExecutionStep("first"), ExecutionStep("second")))

        result = pipeline.execute(request_context, plan)

        self.assertEqual(executed_steps, ["first", "second"])
        self.assertEqual(result.status, ExecutionStatus.SUCCESS)
        self.assertIs(request_context.execution_result, result)

    def test_returns_not_supported_when_a_step_has_no_handler(self) -> None:
        request_context = RequestContext(Request("Test request"))

        result = ExecutionPipeline().execute(
            request_context,
            ExecutionPlan(steps=(ExecutionStep("missing"),)),
        )

        self.assertEqual(result.status, ExecutionStatus.NOT_SUPPORTED)
        self.assertIs(request_context.execution_result, result)

    def test_cancels_confirmation_required_plans_without_executing_steps(self) -> None:
        executed_steps: list[str] = []
        pipeline = ExecutionPipeline(
            {
                "step": RecordingHandler(
                    executed_steps,
                    ExecutionResult(ExecutionStatus.SUCCESS, "Step completed."),
                )
            }
        )

        result = pipeline.execute(
            RequestContext(Request("Test request")),
            ExecutionPlan(
                steps=(ExecutionStep("step"),),
                requires_confirmation=True,
            ),
        )

        self.assertEqual(result.status, ExecutionStatus.CANCELLED)
        self.assertEqual(executed_steps, [])

    def test_returns_partial_when_a_later_step_fails(self) -> None:
        executed_steps: list[str] = []
        pipeline = ExecutionPipeline(
            {
                "first": RecordingHandler(
                    executed_steps,
                    ExecutionResult(ExecutionStatus.SUCCESS, "First completed."),
                ),
                "second": RecordingHandler(
                    executed_steps,
                    ExecutionResult(ExecutionStatus.FAILED, "Second failed.", error="error"),
                ),
            }
        )

        result = pipeline.execute(
            RequestContext(Request("Test request")),
            ExecutionPlan(steps=(ExecutionStep("first"), ExecutionStep("second"))),
        )

        self.assertEqual(executed_steps, ["first", "second"])
        self.assertEqual(result.status, ExecutionStatus.PARTIAL)
        self.assertEqual(result.metadata["completed_steps"], 1)
        self.assertEqual(result.error, "error")
