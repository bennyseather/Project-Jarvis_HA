# M11 Home Assistant Capability Context

M11 creates a bounded Home Assistant context for the language model. It is the
intersection of live discovery and Jarvis configuration: permitted read
entities, permitted action entities, permitted services and their declared
fields, plus aliases that resolve to those entities.

The context intentionally excludes the full Home Assistant inventory,
unconfigured entities, unconfigured services, state history, credentials, and
confirmation tokens. It guides proposal formation only; the existing action
gateway remains the final validator and confirmation authority.

Unknown or ambiguous read/action targets receive a clarification response.
Aliases resolve only to configured targets. Service data is still rejected when
it contains fields not declared by Home Assistant discovery.

## Completed acceptance run

On 2026-07-25, live Home Assistant discovery produced a model capability
snapshot containing only `light.blocks` for configured reads and actions, and
only `light.turn_off` and `light.turn_on` as permitted services. No service was
called during this read-only check.
