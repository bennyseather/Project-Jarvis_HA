# Changelog

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
