# ADR-001 — Project Scope

Status: Accepted

## Context

Project Jarvis operates alongside Home Assistant and a language model. Home Assistant is the authoritative source for the connected home: its devices, entities, automations, integrations, and current state. The language model supplies reasoning, language understanding, planning, and general knowledge. Jarvis complements both by retaining information over time, managing context, coordinating interactions, and maintaining knowledge that is specific to the home.

## Decision

- Home Assistant remains the system of record.
- The language model remains responsible for reasoning and language.
- Jarvis provides persistence, context, orchestration, and home-specific knowledge.
- Jarvis must not duplicate capabilities already provided by Home Assistant or the language model.

## Consequences

Future development must preserve these boundaries. Features should use Home Assistant for home state and control, and use the language model for reasoning and language tasks. Jarvis-focused work should add persistent memory, contextual continuity, orchestration, or home-specific knowledge rather than reimplementing capabilities owned by either system. This keeps the architecture understandable, reduces duplication, and directs milestones toward complementary responsibilities.
