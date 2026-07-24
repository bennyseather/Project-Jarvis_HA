"""Unit tests for execution planning."""

import unittest

from jarvis.execution.execution_planner import ExecutionPlanner
from jarvis.models.capability import AvailableCapability, Capability, CapabilityProvider
from jarvis.models.request import Request, RequestType
from jarvis.models.request_context import RequestContext


class ExecutionPlannerTests(unittest.TestCase):
    """Verify deterministic, provider-neutral execution planning."""

    def test_selects_the_first_available_capability_and_provider(self) -> None:
        capability = Capability(
            "notifications",
            "Support notification requests.",
            frozenset({RequestType.COMMAND}),
        )
        first_provider = CapabilityProvider("notifications", "primary")
        second_provider = CapabilityProvider("notifications", "fallback")
        request_context = RequestContext(
            Request("Send a notification."),
            selected_capabilities=(
                AvailableCapability(capability, (first_provider, second_provider)),
            ),
        )

        plan = ExecutionPlanner().plan(request_context)

        self.assertIs(plan.selected_capability, capability)
        self.assertIs(plan.selected_provider, first_provider)
        self.assertEqual(plan.steps[0].name, "execute_capability")
        self.assertEqual(plan.steps[0].metadata["provider"], "primary")

    def test_returns_an_empty_plan_when_no_capability_is_selected(self) -> None:
        plan = ExecutionPlanner().plan(RequestContext(Request("Hello, Jarvis.")))

        self.assertIsNone(plan.selected_capability)
        self.assertIsNone(plan.selected_provider)
        self.assertEqual(plan.steps, ())
