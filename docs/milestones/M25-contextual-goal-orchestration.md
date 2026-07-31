# M25 Contextual Goal-Based Orchestration

Status: complete

## Outcome

Jarvis can associate an explicitly taught household goal with one or more
Home Assistant actions, explain that meaning, compare it with current state,
and execute only the necessary M24 steps.

## Architecture

- Goal meanings are durable `HOUSEHOLD_PROCEDURE` knowledge records tagged
  `jarvis:contextual-goal`; no separate private store is introduced.
- Goal records contain an explicit name and an M24-compatible command.
- Exact vocabulary matching provides deterministic confidence and evidence.
- Multiple equally specific matches require clarification.
- Current-state filtering removes actions whose desired result is already true.
- Existing scene and script entities can be the complete goal implementation.
- Execution, limits, authorization, confirmation, correction, and recovery are
  delegated to M24.
- Security, lock, and bedtime goal names always force one confirmation.

## User controls

- `teach goal <name> | <actions>`
- `show goals`
- `explain goal <name>`
- `correct goal <name> | <actions>`
- `forget goal <name>`

These records are inspectable, correctable, and permanently deletable. Jarvis
does not invent goal meanings or permissions.

## Boundaries

Goals do not create Home Assistant scenes, scripts, automations, schedules,
loops, or delayed jobs. Home Assistant remains the owner of entities, state,
services, and persistent automation. Plans remain bounded to ten resolved
entity actions.
