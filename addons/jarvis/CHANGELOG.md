# Changelog

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
