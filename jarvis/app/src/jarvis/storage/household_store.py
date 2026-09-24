"""Opt-in owner-scoped explicit memory/preferences; no legacy data migration.

Subjects must come from a trusted server-side adapter. This local SQLite store
does not authenticate callers, encrypt disk, or implement legacy-store forgetting.
"""
import json
import sqlite3
from pathlib import Path
from jarvis.household_access import HouseholdSubject


class HouseholdStore:
    def __init__(self, path, *, known_members):
        self._members = frozenset(known_members)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path)
        self._db.execute('PRAGMA secure_delete = ON')
        with self._db:
            self._db.execute('''CREATE TABLE IF NOT EXISTS household_owner_revision (
                owner TEXT PRIMARY KEY, revision INTEGER NOT NULL)''')
            self._db.execute('''CREATE TABLE IF NOT EXISTS household_private_records (
                owner TEXT NOT NULL, kind TEXT NOT NULL, item_key TEXT NOT NULL,
                value_json TEXT NOT NULL, source TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(owner, kind, item_key))''')

    def _owner(self, subject):
        if not isinstance(subject, HouseholdSubject) or subject.member_id not in self._members:
            raise PermissionError('An identified member is required')
        return subject.member_id

    @staticmethod
    def _validate_key(kind, key):
        if kind not in ('preference', 'memory'):
            raise ValueError('Unsupported record kind')
        if not isinstance(key, str) or not key.strip() or len(key) > 120:
            raise ValueError('Invalid record key')

    def revision(self, subject):
        owner = self._owner(subject)
        row = self._db.execute('SELECT revision FROM household_owner_revision WHERE owner=?', (owner,)).fetchone()
        return row[0] if row else 0

    def _bump(self, owner, expected_revision):
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError('Expected revision required')
        self._db.execute('INSERT OR IGNORE INTO household_owner_revision VALUES (?, 0)', (owner,))
        changed = self._db.execute('UPDATE household_owner_revision SET revision=revision+1 WHERE owner=? AND revision=?', (owner, expected_revision))
        if changed.rowcount != 1:
            raise ValueError('Profile changed; reload before editing')

    def put(self, subject, kind, key, value, *, source, approved, expected_revision):
        owner = self._owner(subject)
        self._validate_key(kind, key)
        if approved is not True:
            raise PermissionError('Explicit approval required')
        if not isinstance(source, str) or not source.strip() or len(source) > 500:
            raise ValueError('Bounded provenance required')
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
        if len(encoded.encode()) > 8192:
            raise ValueError('Record too large')
        with self._db:
            self._bump(owner, expected_revision)
            self._db.execute('''INSERT INTO household_private_records(owner,kind,item_key,value_json,source)
                VALUES (?,?,?,?,?) ON CONFLICT(owner,kind,item_key) DO UPDATE SET
                value_json=excluded.value_json, source=excluded.source, updated_at=CURRENT_TIMESTAMP''',
                (owner, kind, key, encoded, source))
        return self.revision(subject)

    def records(self, subject):
        owner = self._owner(subject)
        rows = self._db.execute('SELECT kind,item_key,value_json,source FROM household_private_records WHERE owner=? ORDER BY kind,item_key', (owner,)).fetchall()
        return [{'kind': k, 'key': key, 'value': json.loads(value), 'source': source}
                for k, key, value, source in rows]

    def forget(self, subject, kind, key, *, expected_revision):
        owner = self._owner(subject)
        self._validate_key(kind, key)
        with self._db:
            self._bump(owner, expected_revision)
            self._db.execute('DELETE FROM household_private_records WHERE owner=? AND kind=? AND item_key=?', (owner, kind, key))
        return self.revision(subject)

    def close(self):
        self._db.close()
