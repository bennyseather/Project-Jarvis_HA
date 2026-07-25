# M8 Event Awareness

M8 provides recent, read-only event awareness without creating a second Home
Assistant history database. The timeline is an in-process bounded buffer and
is discarded when Jarvis stops.

Only event types and entities explicitly listed in `event_timeline` are
accepted. Filtering occurs before an event reaches the timeline. Records retain
only event type, entity ID, occurrence time, and an optional state value; raw
event payloads and attributes are not retained. Timeline events never create
Memory or Learning records and cannot trigger Home Assistant services.

The feature is disabled when `event_timeline.enabled` is absent or false.
When enabled, `timeline` or `timeline <configured entity_id>` shows the most
recent permitted events in the console.

Acceptance configuration uses only `state_changed` events for `light.blocks`.
It uses confirmed `light.turn_off` and `light.turn_on` test actions for that
same safe entity and verifies that the resulting events are visible in the
bounded timeline.

## Completed acceptance run

On 2026-07-25, Jarvis subscribed to the configured Home Assistant event stream
and performed a confirmed off → on cycle for `light.blocks`. The timeline
recorded the `off` and `on` state changes for that entity only. The subscription
remained active throughout the check. No raw event payloads, credentials, or
events from other entities were retained in this record.
