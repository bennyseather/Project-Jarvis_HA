# M29 Adaptive Jarvis Personality

Status: complete

M29 adds a deterministic presentation layer after reasoning, authorization,
risk evaluation, and action execution. It may shape wording and voice length,
but it cannot change facts, selected entities, structured results,
confirmations, permissions, or execution.

Jarvis uses calm British English with configurable warmth, formality,
verbosity, and restrained original humour. Preferred names are used sparingly
and only when explicitly supplied. Approved household knowledge may inform
conversation, but Jarvis does not infer private relationships or retain a
covert psychological profile.

Supported controls are:

- `show personality`
- `show relationship preferences`
- `explain last response style`
- `address me as <name>`
- `set personality humour off|subtle|moderate`
- `set personality warmth reserved|balanced|warm`
- `set personality formality relaxed|refined`
- `set personality verbosity concise|balanced|detailed`
- `forget relationship preferences`
- `reset personality`

Voice responses use shorter, clean sentences suitable for the configured Home
Assistant TTS provider. Confirmations, errors, safety matters, emergencies,
and sensitive topics remain exact and humour-free. Jarvis offers at most one
next step when it is materially useful and avoids repeated openings or
catchphrases.

Home Assistant and the selected TTS integration continue to own audio
generation and speaker routing. The personality is original and does not
imitate Marvel dialogue, a fictional performance, or an actor.
