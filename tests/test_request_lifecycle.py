"""Unit tests for request identity and orchestration lifecycle tracking."""

import unittest
from datetime import datetime, timezone

from jarvis.capabilities.capability_registry import CapabilityRegistry
from jarvis.classification.request_classifier import KeywordRequestClassifier
from jarvis.context.context_assembler import ContextAssembler
from jarvis.execution.execution_pipeline import ExecutionPipeline
from jarvis.execution.execution_planner import ExecutionPlanner
from jarvis.models.capability import CapabilityName, CapabilityProvider
from jarvis.models.execution import ExecutionPlan, ExecutionResult, ExecutionStatus, ExecutionStep
from jarvis.models.request import Request
from jarvis.models.request_context import RequestContext
from jarvis.models.request_state import RequestState
from jarvis.response.response_pipeline import ResponsePipeline


class SuccessfulHandler:
    """A local handler used to complete the lifecycle test."""

    def execute(
        self,
        request_context: RequestContext,
        step: ExecutionStep,
    ) -> ExecutionResult:
        return ExecutionResult(ExecutionStatus.SUCCESS, "Execution completed.")


class RequestLifecycleTests(unittest.TestCase):
    """Verify identity and successful state transitions across EPIC 1."""

    def test_accepts_a_deterministic_request_identifier(self) -> None:
        context = RequestContext(Request("Hello, Jarvis."), request_id="request-123")

        self.assertEqual(context.request_id, "request-123")
        self.assertEqual(context.state, RequestState.RECEIVED)

    def test_tracks_a_request_through_the_orchestration_pipeline(self) -> None:
        context = RequestContext(Request("Turn on the kitchen lights."), request_id="request-1")
        classifier = KeywordRequestClassifier()
        registry = CapabilityRegistry()
        registry.register_provider(
            CapabilityProvider(CapabilityName.HOME_ASSISTANT, "test-provider")
        )

        classifier.classify_context(context)
        self.assertEqual(context.state, RequestState.CLASSIFIED)

        registry.select_for(context)
        self.assertEqual(context.state, RequestState.CAPABILITIES_SELECTED)

        ContextAssembler().assemble(context)
        self.assertEqual(context.state, RequestState.CONTEXT_ASSEMBLED)

        plan = ExecutionPlanner().plan(context)
        self.assertEqual(context.state, RequestState.PLANNED)

        ExecutionPipeline({"execute_capability": SuccessfulHandler()}).execute(context, plan)
        self.assertEqual(context.state, RequestState.COMPLETED)

        ResponsePipeline(
            lambda: datetime(2026, 7, 24, 12, 0, tzinfo=timezone.utc)
        ).process(context)
        self.assertEqual(context.state, RequestState.COMPLETED)

    def test_marks_cancelled_execution_as_cancelled(self) -> None:
        context = RequestContext(Request("Test request"), request_id="request-cancelled")

        ExecutionPipeline().execute(
            context,
            ExecutionPlan(requires_confirmation=True),
        )

        self.assertEqual(context.state, RequestState.CANCELLED)
