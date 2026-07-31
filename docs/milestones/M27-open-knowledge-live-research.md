# M27 Open Knowledge and Live Research

Status: complete

Jarvis now routes general questions through OpenAI reasoning and can invoke
OpenAI's native web-search tool when information is current, niche, uncertain,
externally verifiable, or explicitly requested. Home Assistant remains the
sole owner of entity state and service execution; research grants no device or
external-action authority.

Research answers preserve bounded conversation history, approved memory,
approved knowledge, voice mode, and personality context. URL citations are
extracted as structured source metadata and bounded by configuration. Jarvis
distinguishes sourced facts from inference, handles ambiguous identity
research cautiously, and does not silently turn search findings into memory.

Configuration under `research` controls automatic routing, search context
depth, maximum returned sources, timeout, and optional allowed domains.
Conversation commands include `do not use web research for this conversation`,
`enable web research for this conversation`, `what sources did you use`,
`remember this`, and `forget this`. The final two operate on the most recent
research result and require an explicit user command.
