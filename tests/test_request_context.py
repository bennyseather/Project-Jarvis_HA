"""Unit tests for the orchestration request context."""

import unittest

from jarvis.models.context import ContextPackage
from jarvis.models.execution import ExecutionResult, ExecutionStatus
from jarvis.models.request import Request, RequestClassification, RequestType
from jarvis.models.request_context import RequestContext


class RequestContextTests(unittest.TestCase):
    """Verify that the model supports gradual pipeline enrichment."""

    def test_starts_with_only_the_original_request(self) -> None:
        request = Request("What is the kitchen temperature?")

        context = RequestContext(request)

        self.assertIs(context.request, request)
        self.assertIsNone(context.classification)
        self.assertEqual(context.selected_capabilities, ())
        self.assertIsNone(context.context_package)
        self.assertIsNone(context.execution_result)
        self.assertIsNone(context.response)

    def test_allows_pipeline_stages_to_enrich_the_same_object(self) -> None:
        context = RequestContext(Request("Turn on the kitchen lights."))
        classification = RequestClassification(context.request, RequestType.COMMAND)
        context_package = ContextPackage(metadata={"room": "kitchen"})
        execution_result = ExecutionResult(
            ExecutionStatus.NOT_SUPPORTED,
            "No execution steps are available.",
        )

        context.classification = classification
        context.context_package = context_package
        context.execution_result = execution_result
        context.response = None

        self.assertIs(context.classification, classification)
        self.assertIs(context.context_package, context_package)
        self.assertIs(context.execution_result, execution_result)
        self.assertIsNone(context.response)
