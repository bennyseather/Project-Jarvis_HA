# M22 Proactive Assistance and Routine Intelligence

Status: complete

## Outcome

Jarvis can notice a small set of useful, policy-approved situations and present
them as inspectable suggestions. Suggestions can be explained, postponed,
suppressed, cleared, or explicitly accepted. Jarvis never performs an
unsolicited Home Assistant action.

## Architecture

- Home Assistant owns entities, current state, events, notifications, text to
  speech, automations, and service execution.
- The language model owns language understanding and planning.
- Jarvis owns deterministic opportunity detection, suggestion lifecycle,
  provenance, confidence, expiry, cooldowns, quiet hours, and user feedback.
- M22 consumes only permitted current states, M8's bounded in-memory timeline,
  and non-sensitive M21 reflection records.
- Raw Home Assistant events and unrestricted model inference are not persisted
  as proactive profiles.
- Suggested actions use the existing Home Assistant capability and risk
  gateway. Repetition never grants authorization.

## Detection

The deterministic baseline detects:

- permitted battery sensors at or below the configured threshold;
- non-sensitive uncertainty, contradiction, and follow-up reflection records;
- repeated entity-state transitions in the configured bounded M8 timeline.

Routine candidates are temporary suggestions. They do not create Home
Assistant automations or permanent preferences.

## Policy and privacy

- Sensitive candidates are excluded.
- Confidence, pending-count, expiry, cooldown, snooze, quiet-hour, scan-rate,
  low-battery, and repetition limits are validated at startup.
- Persistent notifications are enabled by configuration.
- Proactive speech is disabled by default and additionally requires the
  existing M20 Home Assistant voice route to be explicitly enabled.
- Delivered channels are recorded to prevent duplicate notifications or
  speech.
- Suppression rules are inspectable and permanently removable.

## Natural controls

- `What needs my attention?`
- `Show pending suggestions`
- `Why are you suggesting that?`
- `Do it`
- `Not now`
- `Never suggest this again`
- `Clear pending suggestions`
- `Show suppressed suggestions`
- `Clear suggestion suppressions`

`Do it` has no effect for informational suggestions. For an actionable
suggestion, the exact proposal is passed to the existing authorization gateway;
the gateway may execute immediately, require confirmation, or refuse it.

## Persistence and migration

SQLite schema version 4 adds durable suggestion and suppression tables. Existing
conversation memory, long-term memory, knowledge, and reflection data are
preserved. Clearing a suggestion or suppression does not retain a hidden copy.

## Acceptance boundary

M22 does not add self-modification, covert profiling, automatic permission
expansion, autonomous automation creation, or claims of consciousness. A
suggestion is not an authorization and cannot execute a device action without
an explicit user response.
