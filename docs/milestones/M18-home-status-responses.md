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

Acceptance testing added a deterministic active read scope. Explicit configured
group and area names are resolved before model routing, and successful reads
retain only their bounded entity identifiers for the current process. Ambiguous
read candidates are likewise retained until the user selects one or says “both.”
This session state is non-durable and never expands the configured permissions.
When an exact reference is absent, a bounded category phrase may match permitted
friendly names by its remaining descriptive words and requested device domain;
for example, “porch lights” can offer two porch light entities without including
a porch camera.

User-facing summaries and clarification choices use Home Assistant friendly
names while keeping entity identifiers in the internal result contract. Every
read path, including pending “both” and “all” follow-ups, enforces the 20-entity
bound before contacting Home Assistant. A failed or oversized new selection
clears prior read scope so a later follow-up cannot reuse stale candidates.

An oversized configured area may retain its reference as a pending narrowing
scope without retaining or reading its entity set. A same-turn phrase such as
“lights belonging to the upstairs office,” or a next-turn phrase such as “all
lights,” filters that area by the explicitly named Home Assistant domain before
the 20-entity bound is applied. A bare configured group name is a read selection
and cannot become an action without an action verb.
Area-by-domain reads exclude aggregate helper entities from their results while
retaining the helper's actual member entities. Directly asking for the helper
still resolves the helper to its members.
