# M23 Whole-Home Situational Intelligence

Status: complete

## Outcome

Jarvis can deterministically answer compound current-state and recent-change
questions across permitted Home Assistant floors, areas, groups, device types,
device classes, and entities. Explicit aggregate actions use the exact selected
entity set and the existing action gateway.

## Architecture

- Home Assistant remains authoritative for floors, areas, devices, entities,
  groups, current state, events, and service execution.
- Jarvis assembles a bounded, ephemeral topology for each relevant request.
- The language model remains the language and planning layer, but it cannot
  invent topology members or broaden a deterministic selection.
- No topology snapshot or raw Home Assistant state is stored durably.
- The existing bounded M8 timeline supplies recent changes.

## Deterministic reasoning

M23 supports:

- floor, area, group, entity, and whole-home scopes;
- light, switch, cover, camera, fan, lock, sensor, button, heater, door,
  window, and battery categories;
- on, off, open, closed, unavailable, unknown, and low-battery filters;
- any/all questions, counts, exceptions, and friendly-name details;
- bounded mixed-domain summaries that do not recite raw sensor values;
- exact continuity for `there`, `them`, `those`, `all`, `both`, and `the rest`;
- recent-change summaries from permitted M8 events;
- explicit filtered actions such as turning off lights that are still on.

Unknown or partial references fall through to the existing deterministic
resolver and clarification path. Large reads are summarized; actions remain
limited by the existing maximum of twenty exact entities.

## Policy and privacy

- Only effective permitted read entities enter the topology.
- Only effective permitted action entities can enter an action proposal.
- Sensitive and excluded entities remain excluded by the existing home access
  policy.
- Entity scans, displayed details, and timeline results have validated bounds.
- When all-entity read access is explicitly active, M8 may use that same
  permitted read set; this does not expand authorization.
- Observations never trigger actions. Actions require explicit action language.

## Conversation and voice

Spatial scope is isolated per conversation. Responses use Home Assistant
friendly names and concise spoken summaries. Conversation continuity is
process-local and does not create durable user memory.

## Acceptance boundary

M23 does not duplicate Home Assistant state, create automations, expand
permissions, infer occupancy or safety beyond available states, persist raw
home activity, or allow the language model to invent device selections.

## Home Assistant acceptance

The release is accepted against the user's actual topology with:

- an area-wide mixed-device status summary;
- a floor-wide filtered status question;
- an any/all follow-up using the same conversation;
- a `the rest` follow-up after a device-type selection;
- a bounded recent-change question;
- one explicit filtered light action using a harmless selected light.
