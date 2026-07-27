# M18 Home Status and Multi-Device Responses

Jarvis resolves a permitted area or group, reads at most 20 member entities in
one Home Assistant state snapshot, and returns a bounded state summary with a
small list of named results. Home Assistant light groups are recognized by
their membership attributes regardless of entity domain. Area membership
honors both direct entity assignments and inherited device assignments.

Duplicate friendly names return at most five deterministic clarification
candidates. Multi-device actions execute per entity and report succeeded and
unavailable entities without exposing internal exceptions. Empty, oversized,
unavailable, and unknown requests fail safely. M18 does not add permissions or
retain state history.

The bounded in-process conversation is sent to the Responses API as alternating
user and assistant messages. Stable orchestration instructions remain separate
from the current request and Home Assistant context. This lets the language
model resolve an unambiguous follow-up such as “all of them?” or “what about the
rest?” while the resolver and policy layer still determine the permitted target.
