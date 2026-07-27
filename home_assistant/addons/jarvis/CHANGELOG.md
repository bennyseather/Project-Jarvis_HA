# Changelog

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
