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

    def observe_turn(self, text, conversation_id):
        """A later unrelated question must not leave a hidden 'yes' proposal."""
        if not conversation_id:return
        value=text.strip().casefold()
        if not re.match(r"^(?:please\s+)?(?:remember|save|note|replace|change|forget|remove|delete|confirm household change|cancel household change|undo last household change|yes\b|no\b|confirm\b|cancel\b|save it\b|keep it\b|that is correct\b|that's correct\b)",value):
            with self.lock:self.pending.pop(str(conversation_id),None)

    def _handle(self, text, conversation_id):
        from jarvis.household_memory import clean, bind_statement, find_note, style_note
        from jarvis.household_speaker import current_speaker
        value = re.sub(r'^please\s+', '', clean(text), flags=re.I)
        normalized = value.casefold()
        key = str(conversation_id) if conversation_id else None
        self.pending={k:p for k,p in self.pending.items() if p['expires']>self.clock()}
        previous = self.pending.get(key)
        if normalized in ('yes','yes please','confirm','save it','keep it','that is correct',"that's correct") and previous:
            if previous.get('speaker') != current_speaker.get().member_id:
                return self.result("Please review the proposed change and say 'confirm household change' to approve it from this shared interface.", 'clarification_required')
            normalized='confirm household change'
        if normalized in ('no','no thanks','cancel','never mind','nevermind') and previous:
            normalized='cancel household change'
        confirmation = normalized == 'confirm household change'
        cancellation = normalized == 'cancel household change'
        undo = normalized == 'undo last household change'
        match = re.match(r'^(?:remember|save|note)\s+(?:that\s+)?(.+)$', value, re.I)
        replacement = re.match(r'^replace household note ([a-f0-9]{8}):\s*(.+)$', value, re.I)
        quoted_replace = re.fullmatch(r'(?:replace|change)\s+["“](.+?)["”]\s+(?:with|to)\s+["“](.+?)["”]', value, re.I)
        deletion = re.fullmatch(r'(?:forget|remove|delete)\s+(?:household\s+)?(?:note\s+)?(.+)',value,re.I)
        if quoted_replace:
            old= find_note(self.profile._data,quoted_replace[1])
            if old is None:
                self.pending.pop(key,None)
                return self.result('I could not identify one saved note with that exact text. Ask me to show household notes first.', 'clarification_required')
            replacement = re.match(r'^replace household note ([a-f0-9]{8}):\s*(.+)$',
                                   'replace household note '+old['id']+': '+quoted_replace[2],re.I)
        routine, routine_error = None, None
        from jarvis import household_activities as activities
        activity,activity_error=None,None
        try:
            bound,binding_error=bind_statement(value,self.profile._data)
            if activities.is_request(value) and binding_error:activity_error=binding_error
            elif bound:activity=activities.proposal(bound,self.profile._data)
        except ValueError as exc:activity_error=str(exc)
        if not replacement and not deletion and not activity and not activity_error:
            try:
                routine = routines.proposal(value)
            except ValueError as exc:
                routine_error = str(exc)
        if not (confirmation or cancellation or undo or match or replacement or deletion or routine or routine_error or activity or activity_error):
            self.observe_turn(text, conversation_id)
            return None
        if not confirmation and not cancellation:
            self.pending.pop(key, None)
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
        if activity_error:
            self.pending.pop(key,None)
            return self.result(activity_error,'clarification_required')
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
                if pending.get('activity'):
                    from jarvis.household_speaker import shared_knowledge_enabled
                    if not shared_knowledge_enabled(self.profile._data):
                        return self.result('Shared activity knowledge is disabled. Nothing was saved.','unavailable')
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
                for field in ('members', 'household_routines', 'conversation_notes', 'routine_overrides', 'activity_profiles'):
                    if field in old:
                        document[field] = deepcopy(old[field])
                    else:
                        document.pop(field, None)
                summary = 'Undo the last conversational household change'
            elif activity:
                if activity.get('unchanged'):return self.result('That activity detail is already saved. Nothing was changed.')
                activities.install(document,activity)
                summary=activity['summary']
            elif deletion:
                self.pending.pop(key, None)
                statement, error = bind_statement(re.sub(r'^that\s+', '', deletion[1], flags=re.I), document)
                if error:return self.result(error, 'clarification_required')
                note=find_note(document, statement)
                if note is None:
                    return self.result('I could not identify one saved note with that exact text or ID. Ask me to show household notes first. Nothing was removed.', 'clarification_required')
                document['conversation_notes']=[n for n in document['conversation_notes'] if n['id']!=note['id']]
                summary='Remove shared note: '+note['text']+'. Undo history is retained; this is not secure erasure'
            elif routine:
                self.pending.pop(key, None)
                if not routines.allowed(document, routines.category(routine)):
                    return self.result('Sharing this schedule category is not enabled. Nothing was saved.', 'unavailable')
                routines.install(document, routine)
                summary = routines.describe(routine)
            else:
                statement = replacement.group(2) if replacement else match.group(1)
                statement,error=bind_statement(statement,document)
                if error:
                    self.pending.pop(key,None)
                    return self.result(error,'clarification_required')
                if re.search(r'\b(she|he|they|her|his|their)\b', statement, re.I):
                    return self.result('Please repeat the fact using names rather than pronouns, so I save it for the right people.', 'clarification_required')
                if len(statement) > 500 or re.search(r'\b(password|api[_ -]?key|access[_ -]?token|private key)\b|\bsk-[A-Za-z0-9_-]{12,}|-----BEGIN .+PRIVATE KEY', statement, re.I):
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
                    if any(clean(n['text']).casefold()==clean(statement).casefold() for n in document.get('conversation_notes',[])):
                        self.pending.pop(key,None)
                        return self.result('I already have that exact household note saved. Nothing was changed.')
                    presentation=style_note(statement,document)
                    prior_preferences=[n for n in document.get('conversation_notes',[]) if presentation and
                        (old_style:=style_note(n['text'],document)) and old_style[0]==presentation[0]]
                    if presentation and len(prior_preferences)>1:
                        return self.result('Several saved answer-length notes already exist for that person. Show household notes, then quote the one to replace or remove. Nothing was changed.','clarification_required')
                    if presentation and len(prior_preferences)==1:
                        prior=prior_preferences[0];old_text=prior['text'];prior['text']=statement
                        summary='Update confirmed answer-length preference from '+old_text+' to '+statement
                        type(self.profile)(document)
                        if len(self.pending)>=100:self.pending.pop(next(iter(self.pending)))
                        self.pending[key]={'document':document,'digest':hashlib.sha256(current).hexdigest(),
                            'summary':summary,'expires':now+300,'routine':None,'speaker':current_speaker.get().member_id}
                        return self.result("Proposed shared household change: "+summary+". Say 'confirm household change' or 'yes' to save, or 'cancel household change'.",'clarification_required')
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
            'summary': summary, 'expires': now + 300, 'routine': routine,
            'activity':bool(activity),
            'speaker': current_speaker.get().member_id}
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
