# M46 — Adaptive Preference Learning

M46 lets Jarvis learn stable household preferences without silently turning
observations into control policy. Repeated explicit preference statements are
stored locally as bounded evidence. Three consistent, confidence-qualified
observations automatically become available to Jarvis reasoning context.

## Architecture

- Home Assistant remains authoritative for entities, state, permissions and
  service execution.
- Jarvis owns the durable preference ledger, evidence, confidence, promotion and
  deletion lifecycle.
- The language model may use promoted preferences for reasoning, but cannot
  write or alter the ledger directly.

## Scope

- Deterministic temperature and lighting preference observations.
- Canonical scope resolution across all Home Assistant areas, configured aliases,
  articles, possessives and unique partial room names.
- Three observations by default before a suggestion is eligible.
- Automatic approval after three consistent safe observations.
- SQLite persistence, bounded evidence and audit history.
- Natural listing, provenance explanation, correction and hard deletion.
- Confidence reset after contradiction and decay for stale unapproved evidence.
- Deny-listed security, credential, alarm, unlocking and spending categories.
- Configurable enablement and bounded policy thresholds.

M46 does not retrain models, modify Jarvis code, infer preferences from guests,
grant Home Assistant permissions or autonomously execute learned actions.
