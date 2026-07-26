# M16 Immediate All-Device Control

## Approved outcome

Jarvis can read every discovered Home Assistant entity and immediately execute compatible, entity-targeted device services. Actions do not require a confirmation token.

## Runtime boundary

- Discovery determines the current entity and service catalog at startup.
- All discovered entities are available unless explicitly removed with `home exclude <entity_id>`.
- A service must target one or more entities in its own device domain. For example, `light.turn_on` may target `light.blocks`; it cannot target a lock.
- Home Assistant control-plane and administrative domains remain unavailable: automations, scripts, backups, add-on management, configuration, updates, logging, notifications, webhooks, and similar system operations.
- Every immediate device action is recorded in the bounded non-content audit.

## Operations

- Use `home review` to confirm all-device mode and see exclusions.
- Use `home exclude <entity_id>` to remove an entity, then restart Jarvis to apply the change.
- Use `home audit [1-50]` to inspect recent actions.
- The model context has a deterministic maximum of 500 entities and services. Authorization itself is based on the full discovered catalog; a user can still use an exact entity ID outside the context bound.

## Acceptance

1. Ask for the state of `light.blocks`.
2. Ask Jarvis to turn on `light.blocks`; it must complete without a confirmation token.
3. Run `home audit` and confirm that it contains the device service, entity, time, and outcome only.
4. Confirm that an administrative request such as running an automation is unavailable.
