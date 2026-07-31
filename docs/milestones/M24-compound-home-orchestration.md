# M24 Compound Home Orchestration

Status: complete

## Outcome

Jarvis can execute bounded multi-action home instructions across permitted
Home Assistant entities. Independent actions run together, explicit `then`
steps run in order, and read-only conditions are checked immediately before
their dependent actions.

## Architecture

- Home Assistant remains the sole owner of entity state and service execution.
- Jarvis builds an ephemeral, typed `CompoundPlan`; it does not create scripts,
  automations, schedules, loops, delayed jobs, or persistent routines.
- Every step resolves through the M23 permitted topology and is validated by
  the existing capability and risk gateways.
- Plans contain no more than ten resolved entity actions.
- A plan containing any confirmation-required step presents one combined
  confirmation based on its highest risk. Confirmations are conversation-bound,
  one-use, and expire after 60 seconds.
- Conditions read current Home Assistant state immediately before each
  execution group. They never infer or mutate state.
- Independent actions run concurrently. Explicit `then` groups run
  sequentially. Jarvis does not claim transactional rollback.
- Results enumerate succeeded, skipped, and failed steps. Partial device
  failures are reported explicitly.

## Supported language

- Multiple actions joined with `and`, commas, or `then`.
- Current-state conditions written as `If <entity> is <state>, <actions>`.
- Exclusions written as `except <entity, area, floor, or group>`.
- Corrections made before confirmation replace and invalidate the pending plan.
- Supported services cover enrolled lights, switches, fans, media players,
  covers, locks, buttons, scenes, scripts, vacuums, and robotic mowers.

## Privacy and safety

Compound orchestration introduces no new permissions, network services,
storage schema, or model-controlled execution route. Unresolved, excessive,
unknown-service, unauthorized, and forbidden plans are rejected before any
step executes. Existing Home Assistant audit records remain authoritative for
individual service calls.

## Acceptance

Automated acceptance covers decomposition, ordering, conditions, exclusions,
combined confirmation, one-use confirmation, correction replacement, limits,
authorization failure, partial outcomes, runtime integration, and add-on
packaging.
