# ADR-002 — Request Identity and Lifecycle

Status: Accepted

## Context

Jarvis orchestrates a request through classification, capability selection, context assembly, execution planning, execution, and response normalization. Without a stable identity and current lifecycle state, these stages cannot be reliably correlated in logs, telemetry, events, or future memory records.

## Decision

- Every RequestContext receives a unique request identifier when it is created. The default identifier factory produces UUID values; callers may provide an explicit identifier for deterministic tests or externally managed correlation.
- Every RequestContext begins in the RECEIVED state.
- Context-oriented orchestration stages update the state after they successfully enrich or process the RequestContext: CLASSIFIED, CAPABILITIES_SELECTED, CONTEXT_ASSEMBLED, PLANNED, EXECUTING, and a terminal state.
- COMPLETED means orchestration reached a terminal outcome and is separate from whether the requested work succeeded. CANCELLED represents an explicit confirmation-required cancellation. FAILED represents an unexpected orchestration error.
- The component that completes a stage owns the state transition for that stage. RequestContext stores only the current state; it does not retain a transition history.

## Consequences

Request identity provides a stable correlation key without adding memory behavior. Lifecycle state makes current pipeline progress observable while ExecutionResult continues to describe the outcome of execution itself. For example, an execution result of NOT_SUPPORTED may still leave the request lifecycle COMPLETED because orchestration handled the request to completion. Future event and memory work can associate records with request_id without changing the orchestration contracts.
