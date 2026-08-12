# D4 Dashboard Refinement and Expansion

D4 extends the established Jarvis HUD without changing Home Assistant's
ownership of entities, history, calendar data, or service execution.

## Delivered scope

- 52 px desktop and 56 px panel light toggles.
- Open and Close cover controls, without a Stop control.
- Washing-machine minutes remaining with optional calculated completion.
- Lazy, cached, bounded sensor history for 1–48 hour windows.
- Calendar, Glance, Home Alerts, Network / NAS, Climate Overview, Security
  Perimeter, and Energy Flow cards, all configured through visual editors.
- Global calendar, appointment, storage, safety, perimeter, and energy-flow
  icons in the `jarvis:` icon set.

History and calendar requests use Home Assistant's authenticated API, begin
only near the viewport, cache for sixty seconds, and render bounded results.
No entity IDs are hardcoded and no state leaves Home Assistant.
