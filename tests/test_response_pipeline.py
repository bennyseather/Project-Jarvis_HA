"""Unit tests for the response pipeline."""

import unittest
from dataclasses import replace
from datetime import datetime, timezone

from jarvis.models.execution import ExecutionResult, ExecutionStatus
from jarvis.models.request import Request
from jarvis.models.request_context import RequestContext
from jarvis.models.response import Response, ResponseStatus
from jarvis.response.response_pipeline import ResponsePipeline


FIXED_TIMESTAMP = datetime(2026, 7, 24, 12, 0, tzinfo=timezone.utc)


class TaggingRenderer:
    """A test renderer that demonstrates protocol-based rendering."""

    def render(self, response: Response) -> Response:
        return replace(response, metadata={**response.metadata, "rendered": True})


class ResponsePipelineTests(unittest.TestCase):
    """Verify provider-neutral execution-result normalization."""

    def test_normalizes_success_and_stores_the_response(self) -> None:
        request_context = RequestContext(Request("Test request"))
        request_context.execution_result = ExecutionResult(
            ExecutionStatus.SUCCESS,
            "Execution completed successfully.",
            metadata={"completed_steps": 1},
        )
        pipeline = ResponsePipeline(lambda: FIXED_TIMESTAMP)

        response = pipeline.process(request_context)

        self.assertEqual(response.status, ResponseStatus.SUCCESS)
        self.assertEqual(response.summary, "success")
        self.assertEqual(response.detailed_message, "Execution completed successfully.")
        self.assertEqual(response.metadata["completed_steps"], 1)
        self.assertEqual(response.timestamp, FIXED_TIMESTAMP)
        self.assertIs(request_context.response, response)

    def test_adds_confirmation_for_cancelled_execution(self) -> None:
        request_context = RequestContext(Request("Test request"))
        request_context.execution_result = ExecutionResult(
            ExecutionStatus.CANCELLED,
            "Execution requires confirmation.",
        )

        response = ResponsePipeline(lambda: FIXED_TIMESTAMP).process(request_context)

        self.assertEqual(response.status, ResponseStatus.CANCELLED)
        self.assertIsNotNone(response.confirmation_request)
        self.assertEqual(response.confirmation_request.action, "confirm_execution")

    def test_handles_missing_execution_result_without_external_calls(self) -> None:
        response = ResponsePipeline(lambda: FIXED_TIMESTAMP).process(
            RequestContext(Request("Test request"))
        )

        self.assertEqual(response.status, ResponseStatus.NOT_SUPPORTED)
        self.assertEqual(response.detailed_message, "No execution result is available.")

    def test_uses_the_configured_renderer_protocol(self) -> None:
        request_context = RequestContext(Request("Test request"))
        request_context.execution_result = ExecutionResult(
            ExecutionStatus.FAILED,
            "Execution failed.",
        )

        response = ResponsePipeline(
            lambda: FIXED_TIMESTAMP,
            renderer=TaggingRenderer(),
        ).process(request_context)

        self.assertTrue(response.metadata["rendered"])
        self.assertEqual(response.follow_up_actions[0].name, "retry_execution")
