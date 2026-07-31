# M30 Episodic Conversation Continuity

Status: complete

M30 adds durable, bounded conversation summaries without retaining raw
transcripts. Automatic summaries use a local deterministic topic extractor and
are created only for low-sensitivity conversations. Explicitly requested
summaries may use Luna through the existing AI budget ledger to preserve useful
decisions and unresolved next steps.

Routine summaries expire after 30 days by default. Explicitly pinned summaries
remain until deleted. The store is capped at 50 episodes; if every slot is
pinned, Jarvis refuses another episode rather than silently removing one.

Sensitive conversations are never stored automatically and require the normal
memory-confirmation flow. Stored metadata contains only the conversation
identifier, message count, lifecycle flags, and bounded tags. It does not
contain transcript text, prompts, model responses, audio, or hidden reasoning.

Supported controls are:

- `what were we discussing?`
- `what did we decide about <topic>?`
- `show recent conversations`
- `remember this conversation`
- `pin this conversation`
- `forget this conversation`
- `forget conversations about <topic>`
- `clear conversation history`

Hard deletion removes summaries without tombstones. Episodes may inform later
language context, but they cannot prove current Home Assistant state, grant
permissions, bypass confirmation, or autonomously execute an action.
