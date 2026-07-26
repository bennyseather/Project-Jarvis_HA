# M15 Everyday Assist Experience

## Outcome

M15 makes the deployed Home Assistant conversation agent practical to operate day-to-day while preserving Jarvis's explicit authorization boundary.

## M15.1 Assist command routing

Explicit Jarvis management commands run through the same Assist path as ordinary requests. They remain deterministic commands; they are not sent to the language model.

## M15.2 Clear outcomes and recovery

Assist uses stable, user-facing responses for unavailable services, forbidden actions, expired confirmations, clarifications, and unsupported requests. Internal exception text is not exposed to the user.

## M15.3 Confirmed action audit

Every executed device action records only:

- timestamp;
- authorized service domain and name;
- authorized entity IDs;
- outcome (`success`, `forbidden`, or `unavailable`); and
- a coarse non-sensitive failure code when applicable.

The audit never stores user utterances, model prompts or responses, API keys, service data, memory, knowledge, camera content, or Home Assistant state. Review it through `home audit [1-50]`.

## M15.4 Operations

At startup Jarvis logs effective authorization counts, the durable-policy source, and bridge readiness without printing secrets. Normal operations are:

1. Use the add-on Store's **Update** button, then restart the add-on.
2. In Assist, use `home review` to inspect enabled access and `home exclude <entity_id>` to remove an entity immediately.
3. Use `home audit` to view recent device actions; it is deliberately bounded to 50 records per request.
4. Verify a release with a read and action request for an entity you choose.
5. If a request reports an unavailable service, restart the add-on and confirm the Home Assistant URL, bridge key, and policy file configuration. Do not paste secrets into chat or logs.

## Out of scope

This milestone does not add unrestricted Home Assistant access, automatic actions, raw conversation logging, camera analysis, or action history containing sensitive request content.
