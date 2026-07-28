# Changelog

## 0.9.1

- Render the Jarvis Camera card as an automatic Home Assistant live camera
  stream without requiring the user to open More Info.
- Preserve a local five-second snapshot fallback if the live card helper is
  unavailable.
- Add the same squared, chamfered HUD frame and segmented corners to the
  Jarvis Voice control node used by the rest of the card system.

## 0.9.0

- Add the complete D2 Jarvis UI Design System.
- Replace rounded presentation with squared, lightly chamfered HUD panels.
- Add shared cyan, amber, green, and red interface states with consistent
  hover, focus, touch, unavailable, and reduced-motion behavior.
- Add visually editable Button, Entity, Light, Switch, Slider, Climate, Cover,
  Media, Camera, Sensor, Security, Status, and Voice cards.
- Add an original `jarvis:` SVG icon set with automatic domain and
  device-class mapping and safe Home Assistant icon fallback.
- Add an Icon Catalog, local Entity Coverage audit, and component dashboard.
- Preserve the D1 card resource as a backward-compatible loader.
- Add an optional HACS Dashboard publication package without introducing a
  third-party runtime dependency.

## 0.8.2

- Add a locally bundled animated Jarvis voice card with microphone, interface
  rings, and responsive signal bars.
- Launch the preferred Home Assistant Assist pipeline through the supported
  dashboard action interface.
- Add matching Jarvis action cards for navigation and administration.
- Refine card depth, borders, hover states, typography, and panel styling.
- Preserve native Home Assistant entity tiles for device state and control.
- Add keyboard activation, reduced-motion support, resource registration, and
  upgrade instructions.

## 0.8.1

- Add the optional Jarvis Command Center Home Assistant UI pack.
- Add five responsive native dashboard views for command, rooms, environment,
  media and voice, and Jarvis administration.
- Add desktop and portrait Jarvis themes with original background artwork.
- Add a direct preferred-pipeline Assist launcher.
- Add Home Assistant OS installation, entity-mapping, update, and removal
  instructions.
- Keep the add-on isolated from Home Assistant configuration; UI installation
  remains an explicit user-controlled operation.

## 0.8.0

- Add durable, inspectable reflection records derived only from approved memories.
- Link related people, rooms, routines, preferences, and projects using bounded deterministic context.
- Detect conflicting repeated context and request an explicit correction instead of silently replacing it.
- Track low-confidence memories and relevant follow-ups without unsolicited notifications.
- Learn explicit response-style feedback immediately and keep it subordinate to privacy and safety.
- Consolidate exact duplicate memories without retaining deleted history.
- Add natural controls for learning opt-out, uncertainty, connections, provenance, and connected hard deletion.
- Migrate the durable SQLite schema transactionally while preserving existing memory.

## 0.7.1

- Match Companion microphone requests through either the direct device identity or an Assist satellite's registered device.
- Retry external TTS with provider defaults when a configured language or voice is unsupported.
- Reconnect once when a current-state read encounters a stale Home Assistant websocket.
- Resolve an unambiguous partial area phrase such as "all the office lights" deterministically.
- Add focused external-routing diagnostics while preserving local speech fallback.

## 0.7.0

- Add configurable Home Assistant-owned external voice output.
- Route only the selected microphone device to the selected TTS provider and media player.
- Preserve typed Assist while preventing duplicate local and external speech.
- Add voice-friendly response formatting and safe local fallback.
- Add session-bound natural yes, confirm, no, and cancel responses.
- Add the original calm, British-inspired Jarvis voice-character guidance.

## 0.6.0

- Add durable, conversation-isolated short-term memory using Home Assistant conversation IDs.
- Retain at most 20 conversations or 72 hours, with 100 messages per conversation and a 20-message model context.
- Promote schema-validated stable user context after three distinct repetitions.
- Require confirmation before sensitive information becomes durable memory.
- Add natural remember, recall, provenance, correction, forgetting, learned-memory, and recent-conversation controls.
- Preserve existing memory through a transactional SQLite schema upgrade.
- Add a centralized, configurable Jarvis character profile subordinate to privacy and safety.

## 0.5.7

- Exclude Home Assistant helper-group entities when reading all devices of one domain in an area.
- Keep the actual member lights, including individually area-assigned lights such as Blocks.

## 0.5.6

- Narrow oversized areas by an explicitly requested device domain on the same or next turn.
- Treat a bare configured group name as a read selection, never an implicit action.
- Preserve specific clarification text through the Home Assistant conversation bridge.

## 0.5.5

- Display Home Assistant friendly names in state summaries and clarifications.
- Reject oversized pending follow-ups before reading Home Assistant.
- Clear stale read context when a new explicit selection is unknown or oversized.
- Report the number of permitted entities when an area must be narrowed.

## 0.5.4

- Match bounded category phrases such as “porch lights” to permitted friendly names.
- Keep domain words as filters so light requests cannot select porch cameras or sensors.

## 0.5.3

- Resolve explicit group and area status questions before model routing.
- Expand light-group entity IDs to their member entities.
- Retain the last successful read scope for “them,” “there,” and “all of them.”
- Retain ambiguous read candidates so “both” reads every offered entity.

## 0.5.2

- Send bounded session history to OpenAI as real alternating conversation messages.
- Keep orchestration instructions separate from the current request and home context.
- Resolve clear follow-ups such as “all of them?” and “what about the rest?” without changing a status question into an action.

## 0.5.1

- Recognize Home Assistant light groups by membership, not only `group.*`.
- Resolve areas assigned directly to entities or inherited from devices.
- Read multi-device state from one bounded Home Assistant snapshot.
- Return deterministic candidates for duplicate friendly names.
- Report partial multi-device action outcomes.

## 0.5.0

- Add bounded area and group status summaries.
