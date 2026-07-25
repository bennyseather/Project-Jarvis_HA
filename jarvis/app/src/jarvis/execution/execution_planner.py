"""Deterministic planning of generic execution work."""

from __future__ import annotations

from jarvis.models.execution import ExecutionPlan, ExecutionStep
from jarvis.models.request_context import RequestContext
from jarvis.models.request_state import RequestState


class ExecutionPlanner:
    """Create provider-neutral execution plans from available capabilities."""

    def plan(self, request_context: RequestContext) -> ExecutionPlan:
        """Select the first available capability and provider, if any."""

        try:
            if not request_context.selected_capabilities:
                plan = ExecutionPlan()
            else:
                available_capability = request_context.selected_capabilities[0]
                selected_provider = available_capability.providers[0]

                step = ExecutionStep(
                    name="execute_capability",
                    metadata={
                        "capability": available_capability.capability.name,
                        "provider": selected_provider.provider_id,
                    },
                )

                plan = ExecutionPlan(
                    selected_capability=available_capability.capability,
                    selected_provider=selected_provider,
                    steps=(step,),
                )
        except Exception:
            request_context.state = RequestState.FAILED
            raise

        request_context.state = RequestState.PLANNED
        return plan
