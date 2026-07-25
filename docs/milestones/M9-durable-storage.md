# M9 Durable Storage and Restart Resilience

M9 stores approved Memory and curated Knowledge in a local SQLite database.
The configured database path defaults to `data/jarvis.sqlite3` and is created
locally when Jarvis starts.

Only Memory and Knowledge records are persisted. Conversation history,
confirmation tokens, Home Assistant state/history, and the M8 event timeline
remain process-local and are not stored in this database.

The database has a schema-version table and separate Memory and Knowledge
record tables. Hard deletion performs a physical row delete. Corrections update
the current row, replacing old content without a history or tombstone.

## Operator runbook

1. Stop Jarvis before copying `data/jarvis.sqlite3` for a backup.
2. Store backups as private local files; they contain approved Memory and
   Knowledge content.
3. Restore by stopping Jarvis, replacing the configured database file with the
   backup, then restarting.
4. Do not place the database in cloud-sync storage unless a separate data and
   encryption decision has been approved.
5. SQLite file permissions follow the operating-system account that runs
   Jarvis. Encryption at rest and key management are deliberately out of scope.
