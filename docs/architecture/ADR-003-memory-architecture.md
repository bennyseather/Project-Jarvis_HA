# ADR-003 — Memory Architecture, Privacy, and Lifecycle

Status: Accepted

## Context

Jarvis needs durable, user-relevant knowledge to improve future assistance. Memory must remain distinct from Home Assistant state, operational history, and complete conversation transcripts. It must also remain optional: requests can be handled without reading or writing memory.

The existing ConversationManager is a placeholder and is not the owner of durable memory loading, storage, retrieval, retention, or deletion. Future durable-memory access must use the approved Memory subsystem interfaces.

## Decision

### Memory Taxonomy

The initial taxonomy is:

| Type | Purpose | Initial release |
| --- | --- | --- |
| Preference | Explicit user preferences that guide future assistance. | Eligible when explicit and non-sensitive. |
| Fact | Stable, household- or user-relevant facts. | Eligible when explicit and non-sensitive. |
| Instruction | Stable user instructions for Jarvis. | Eligible when explicit and non-sensitive. |
| Project | Durable context about an ongoing project. | Eligible when explicit and non-sensitive. |
| Episodic | A bounded record of an interaction or event. | Reserved for a later milestone. |
| Conversation summary | A useful summary of prior conversation. | Reserved for a later milestone. |

Corrections are an operation on an existing memory, not an independent automatic memory type. Jarvis must not duplicate Home Assistant state, devices, automations, integrations, or Home Assistant-owned operational history.

### Memory Record Contract

The future provider-neutral MemoryRecord contract contains:

| Field | Required | Notes |
| --- | --- | --- |
| `memory_id` | Yes | Opaque, unique identifier. |
| `memory_type` | Yes | One value from the memory taxonomy. |
| `content` | Yes for persisted records | Durable information supplied or confirmed by the user. |
| `source` | Yes | Provenance category, such as explicit user request or correction. |
| `source_request_id` | When request-originated | Correlates memory work to RequestContext. |
| `created_at` | Yes | Creation timestamp. |
| `updated_at` | Yes | Last replacement or update timestamp. |
| `expires_at` | No | Reserved for future temporary retention; unused initially. |
| `importance` | No | Future retrieval signal. |
| `confidence` | No | Future retrieval signal. |
| `tags` | No | User- or system-approved classification labels. |
| `consent_level` | Yes | Explicit consent or sensitive-information confirmation. |
| `status` | Yes | Memory lifecycle state. |
| `metadata` | No | Non-content, extensible provider-neutral attributes. |

The contract is typed when implemented, but this ADR does not introduce production models or storage.

### Provenance and Correlation

Every persisted memory must identify a provenance source. Initial supported sources are explicit user requests and user corrections. Future sources may include confirmed conversation summaries, imported knowledge, and learned preferences, but they are not enabled initially.

Memory work originating from an orchestration request must record the associated `request_id`. Memory operations must also use `memory_id` and timestamps. Provenance must remain sufficient to explain why a record exists without duplicating the full conversation transcript.

### Consent Policy

- Persist only explicit memories that a user directly asks Jarvis to remember.
- Persist only non-sensitive information by default.
- Disable inferred-memory persistence in the initial release.
- Do not silently convert conversation content, preferences, corrections, summaries, or observations into durable memory.
- Sensitive personal information requires an explicit confirmation step before persistence.
- Memory writing remains policy-controlled even when a user invokes an explicit memory capability.

### Retention Policy

- Explicit durable memory remains stored until the user corrects or deletes it.
- The initial release does not persist session-only or temporary information.
- Episodic and conversation-summary memory are reserved for later milestones.
- No automatic expiration applies to durable explicit memory in the initial release.
- `expires_at` is optional and reserved for an approved future retention policy.

### Deletion and Correction

- Forgetting one memory, matching memories, or all memories is an explicit subsystem capability.
- Initial deletion is a hard delete of the complete record, including content and associated metadata.
- Deleted memory is not retrievable, searchable, restorable, or available to Context Assembly.
- No tombstone containing the deleted value is retained.
- A future audit system may retain only a non-content operation reference: operation type, timestamp, request_id, and an opaque memory identifier or one-way reference. It must never retain deleted content or reconstructable metadata.
- Correcting a memory replaces or updates the existing durable record. The prior content is not retained initially and no undisclosed competing fact is created.
- Historical versioning or retained superseded content requires a separate privacy decision.

### Memory Lifecycle

The future MemoryStatus contract includes `ACTIVE`, `SUPERSEDED`, `EXPIRED`, `REJECTED`, and `PENDING_CONFIRMATION`. `DELETED` is intentionally excluded because hard deletion does not leave a retrievable record.

The initial release persists only `ACTIVE` records. Sensitive information awaiting confirmation must not become durable memory. `DELETED` is an operation outcome, not a retained record, because deletion is hard. `SUPERSEDED`, `EXPIRED`, and `REJECTED` are reserved for future approved workflows.

### Provider-Neutral Interfaces

Future implementations use provider-neutral contracts:

- `MemoryStore` owns physical persistence and hard deletion: create, get, update, delete, and inspect/list records.
- `MemoryRetriever` accepts a retrieval query and returns ranked, policy-eligible records.
- `MemoryWriter` creates explicit memories and applies user corrections only after a policy decision.
- `MemoryPolicy` evaluates consent, sensitivity, retention eligibility, and write or retrieval permission.

Deletion and updates belong to `MemoryStore` because the storage backend must guarantee physical removal and atomic replacement. `MemoryWriter` orchestrates approved writes; it does not bypass policy or storage semantics.

### Retrieval Contract

A future retrieval query may include request text, request classification, `request_id`, requested memory types, tags, result limit, and user privacy settings. Retrieval ranking may later consider relevance, importance, recency, memory type, and expiration. The result returns policy-eligible MemoryRecords with provider-neutral retrieval metadata such as relevance score.

Embeddings, semantic search, and automatic inference are not part of this decision or the initial implementation.

### Orchestration Integration

The approved future flow is:

```text
RequestContext
  → Classification
  → Capability selection
  → Memory retrieval during Context Assembly
  → Execution
  → Optional policy-controlled memory-writing decision after a successful outcome
  → Response
```

- Context Assembly may retrieve relevant memory through `MemoryRetriever` and place approved results in `ContextPackage.memory`.
- Execution must not query storage unless it is executing an explicitly approved memory capability.
- Response Pipeline must not write memory.
- A dedicated MemoryWriter or policy-controlled writing stage owns persistence.
- Context Assembly does not depend directly on ConversationManager.

## Consequences

Memory remains an optional, policy-controlled subsystem with traceable provenance. The architecture supports replacing storage backends without changing orchestration logic. The initial privacy posture favors explicit, non-sensitive, user-controlled durable information over automatic collection. Future memory expansion requires approval before enabling inference, temporary retention, summaries, episodic records, historical versioning, or audit infrastructure.
