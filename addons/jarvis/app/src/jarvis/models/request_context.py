"""The request context shared by Jarvis orchestration components."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from jarvis.models.capability import AvailableCapability
from jarvis.models.context import ContextPackage
from jarvis.models.execution import ExecutionResult
from jarvis.models.request import Request, RequestClassification
from jarvis.models.response import Response
from jarvis.models.request_state import RequestState


def generate_request_id() -> str:
    """Create an identifier for a newly received request."""

    return str(uuid4())


@dataclass(slots=True)
class RequestContext:
    """Structured request data enriched by each orchestration stage."""

    request: Request
    request_id: str = field(default_factory=generate_request_id)
    state: RequestState = RequestState.RECEIVED
    classification: RequestClassification | None = None
    selected_capabilities: tuple[AvailableCapability, ...] = field(default_factory=tuple)
    context_package: ContextPackage | None = None
    execution_result: ExecutionResult | None = None
    response: Response | None = None
