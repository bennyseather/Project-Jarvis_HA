"""Explicit shared-household edits. No model-generated writes or device actions."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from threading import RLock
from jarvis import household_routines as routines
import time
import uuid


class HouseholdEdits:
    def __init__(self, profile, *, clock=time.monotonic):
        self.profile, self.clock = profile, clock
        self.pending = {}
        self.lock = RLock()

    @staticmethod
    def result(message, status='success'):
        return {'status': status, 'message': message, 'provider': 'household_edits', 'cacheable': False}

    def handle(self, text, conversation_id):
        with self.lock:
            return self._handle(text, conversation_id)

    def _handle(self, text, conversation_id):
        value = text.strip().rstrip('.!?')
        normalized = value.casefold()
        confirmation = normalized == 'confirm household change'
        cancellation = normalized == 'cancel household change'
        undo = normalized == 'undo last household change'
        match = re.match(r'^(?:remember|save|note)\s+(?:that\s+)?(.+)$', value, re.I)
        replacement = re.match(r'^replace household note ([a-f0-9]{8}):\s*(.+)$', value, re.I)
        routine, routine_error = None, None
        if not replacement:
            try:
                routine = routines.proposal(value)
            except ValueError as exc:
                routine_error = str(exc)
        if not (confirmation or cancellation or undo or match or replacement or routine or routine_error):
            return None
        policy = self.profile._data.get('conversational_updates', {})
        if policy.get('mode') != 'shared_confirmation' or not policy.get('source'):
            return self.result('Conversational household saving is not enabled.', 'unavailable')
        if not conversation_id:
            return self.result('A stable conversation is required to propose and confirm a household change.', 'clarification_required')
        key = str(conversation_id)
        now = self.clock()
        self.pending = {k: p for k, p in self.pending.items() if p['expires'] > now}
        if routine_error:
            self.pending.pop(key, None)
            return self.result(routine_error, 'clarification_required')
        if cancellation:
            self.pending.pop(key, None)
            return self.result('Household change cancelled. Nothing was saved.')
        path = getattr(self.profile, '_source_path', None)
        if path is None:
            return self.result('The persistent household profile is unavailable. Nothing was saved.', 'unavailable')
        path = Path(path)
        if confirmation:
            pending = self.pending.pop(key, None)
            if pending is None:
                return self.result('There is no pending household change in this conversation. Please repeat the change.', 'clarification_required')
            try:
                current = path.read_bytes()
                if hashlib.sha256(current).hexdigest() != pending['digest']:
                    return self.result('The profile changed since this proposal. Please repeat your change so it can be checked again.', 'clarification_required')
                document = pending['document']
                record = pending.get('routine')
                if record and record['kind'] == 'no_school' and record['on'] < routines.today().isoformat():
                    return self.result('That exception date has passed. Please repeat the change with a current date.', 'clarification_required')
                document['revision'] = self.profile._data['revision'] + 1
                stamp = datetime.now(timezone.utc).isoformat()
                document.setdefault('household_edit_audit', []).append({
                    'revision': document['revision'], 'at': stamp,
                    'actor': 'shared HA user; personal identity not verified',
                    'summary': pending['summary'], 'before': pending['digest']})
                document['household_edit_audit'] = document['household_edit_audit'][-50:]
                validated = type(self.profile)(document)
                history = path.parent / (path.name + '.history')
                history.mkdir(mode=0o700, exist_ok=True)
                backup = history / (pending['digest'] + '.json')
                if not backup.exists():
                    self._atomic(backup, current)
                encoded = json.dumps(document, ensure_ascii=False, indent=2).encode('utf-8')
                if len(encoded) > 131072:
                    raise ValueError('Profile size limit')
                self._atomic(path, encoded)
                self.profile._data = validated._data
            except Exception:
                return self.result('The household change could not be saved. No success has been recorded; please retry.', 'unavailable')
            return self.result(f"Saved household change (revision {document['revision']}): {pending['summary']} You can say 'undo last household change'. No devices or alarms were changed.")
        try:
            current = path.read_bytes()
            document = json.loads(current)
            if document['revision'] != self.profile._data['revision']:
                return self.result('The profile was changed outside this session. Reload it before editing.', 'unavailable')
            if undo:
                audit = document.get('household_edit_audit', [])
                if not audit:
                    return self.result('There is no conversational household change to undo.', 'clarification_required')
                digest = audit[-1]['before']
                if not re.fullmatch(r'[a-f0-9]{64}', digest):
                    raise ValueError('Invalid history reference')
                old = json.loads((path.parent / (path.name + '.history') / (digest + '.json')).read_text())
                # Undo data only, never permissions or source bindings.
                for field in ('members', 'household_routines', 'conversation_notes', 'routine_overrides'):
                    if field in old:
                        document[field] = deepcopy(old[field])
                    else:
                        document.pop(field, None)
                summary = 'Undo the last conversational household change'
            elif routine:
                self.pending.pop(key, None)
                if not routines.allowed(document, routines.category(routine)):
                    return self.result('Sharing this schedule category is not enabled. Nothing was saved.', 'unavailable')
                routines.install(document, routine)
                summary = routines.describe(routine)
            else:
                statement = replacement.group(2) if replacement else match.group(1)
                if re.search(r'\b(she|he|they|her|his|their)\b', statement, re.I):
                    return self.result('Please repeat the fact using names rather than pronouns, so I save it for the right people.', 'clarification_required')
                if len(statement) > 500 or re.search(r'\b(password|api[_ -]?key|access[_ -]?token|private key)\b', statement, re.I):
                    return self.result('Keep household notes under 500 characters and do not include passwords or access keys.', 'clarification_required')
                if replacement:
                    identifier = replacement.group(1).lower()
                    note = next((n for n in document.get('conversation_notes', []) if n['id'] == identifier), None)
                    if note is None:
                        return self.result('That household note ID was not found.', 'clarification_required')
                    note['text'] = statement
                    summary = f'Replace shared note {identifier}: {statement}'
                elif re.search(r'\bmia\b', statement, re.I) and re.search(r'\bemrik\b', statement, re.I) and re.search(r'\bschool\b', statement, re.I) and re.search(r'\b(no school|neither|neiter|do not have school|don.t have school)\b', statement, re.I) and (re.search(r'\bweekends?\b', statement, re.I) or (re.search(r'\bsaturdays?\b', statement, re.I) and re.search(r'\bsundays?\b', statement, re.I))):
                    for member in document['members']:
                        if member['id'] == 'mia':
                            member['schedule']['school']['exceptions'] = 'No school on Saturdays or Sundays. Holidays and exceptional weekdays are not verified; a schedule does not prove actual attendance.'
                        elif member['id'] == 'emrik':
                            member['education_and_routine']['exceptions'] = 'No school on Saturdays or Sundays. Holidays, live bus service and actual attendance are not verified.'
                    summary = 'Mia and Emrik have no school on Saturdays or Sundays'
                else:
                    identifier = uuid.uuid4().hex[:8]
                    notes = document.setdefault('conversation_notes', [])
                    if len(notes) >= 100:
                        return self.result('The shared note limit has been reached. Replace an existing note instead.', 'clarification_required')
                    notes.append({'id': identifier, 'text': statement})
                    summary = f'Add shared note {identifier}: {statement}. This adds a note; it does not replace structured schedules'
            type(self.profile)(document)
        except Exception:
            return self.result('I could not prepare that household change. Nothing was saved.', 'unavailable')
        if len(self.pending) >= 100:
            self.pending.pop(next(iter(self.pending)))
        self.pending[key] = {'document': document, 'digest': hashlib.sha256(current).hexdigest(),
            'summary': summary, 'expires': now + 300, 'routine': routine}
        return self.result(f"Proposed shared household change: {summary}. Anyone using the shared interface can approve it. Say 'confirm household change' to save, or 'cancel household change'.", 'clarification_required')

    @staticmethod
    def _atomic(path, content):
        temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
        try:
            with open(temporary, 'xb') as stream:
                os.chmod(temporary, 0o600)
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if temporary.exists():
                temporary.unlink()
