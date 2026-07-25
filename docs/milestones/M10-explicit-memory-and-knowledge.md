# M10 Explicit Memory and Knowledge Experience

M10 adds deterministic console commands for user-controlled durable data. They
run before the language-model request path and use the existing policy-controlled
writers and stores.

## Commands

- `memory remember <content>`
- `memory remember-sensitive <content>` then `memory confirm <token>`
- `memory list`
- `memory correct <memory-id> | <replacement content>`
- `memory forget <memory-id>`
- `memory forget-sensitive <memory-id>` then `memory confirm-delete <token>`
- `knowledge add <content>`
- `knowledge list`
- `knowledge correct <knowledge-id> | <replacement content>`
- `knowledge forget <knowledge-id>`

Sensitive memory has no durable record until its separate confirmation command
succeeds. Memory deletion is a hard delete. Corrections replace stored content.
Knowledge accepts only explicit, non-sensitive content. IDs are returned by
create/list operations for later correction or deletion.
