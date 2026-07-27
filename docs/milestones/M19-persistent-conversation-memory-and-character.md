# M19 Persistent Conversation Memory and Character

Status: complete

## Outcome

Jarvis now retains bounded recent conversations, learns carefully from repeated
user-authored context, preserves durable memory across add-on upgrades, and uses
a centralized original character profile.

## Architecture

- Home Assistant `conversation_id` is carried through the custom component and
  local authenticated bridge into the runtime.
- Short-term messages are stored in the existing `/config/jarvis.sqlite3`
  database and isolated by conversation.
- Retention applies both limits: no more than the newest 20 conversations and
  no conversation older than 72 hours. Each conversation is capped at 100
  messages and only the newest 20 enter an OpenAI request.
- The M19 SQLite migration is transactional and advances the schema from
  version 1 to version 2 without modifying existing explicit memory or
  knowledge records.
- Repeated-context extraction is schema validated. Only user assertions about
  stable facts, preferences, routines, relationships, names, or home
  terminology qualify.
- Three distinct qualifying user messages are required. Device state,
  commands, questions, temporary plans, assistant replies, and unsupported
  inference are excluded.
- Automatically learned records carry `repeated_user_context` provenance and
  are deduplicated. Sensitive candidates require a separate confirmation.
- Natural controls support remembering, recalling, provenance, listing
  automatically learned memory, correcting, forgetting, and clearing recent
  conversations. Existing technical memory commands remain available.
- Persona behavior is centralized and configurable. It is subordinate to
  privacy, authorization, safety, factual Home Assistant state, and honest
  uncertainty.

## Privacy and lifecycle

- Recent conversation content is automatically hard-deleted when either
  retention boundary is exceeded.
- Durable memory remains until corrected or hard-deleted.
- Corrections replace content without retaining history.
- Sensitive durable memory is not created without confirmation.
- Action confirmations and deterministic follow-up state are bound to the
  originating conversation.

## Acceptance

Automated coverage verifies retention, restart survival, versioned migration
from a pre-M19 database, third-occurrence promotion, deduplication, sensitive
confirmation, natural controls, and persona safety precedence.
