"""Durable, explicitly confirmed household reminders, not device automation.

Delivery is an idempotent HA persistent notification, never unsolicited speech.
Only confirmed requests create rows. Single-process store, atomic replace/fsync,
revision conflict checks, and no silent recovery of corrupt files.
"""
import asyncio
from collections import OrderedDict
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import secrets
import tempfile
from threading import RLock
import time
from zoneinfo import ZoneInfo

from jarvis.household_memory import clean, result
from jarvis.household_planning import resolve_dates
from jarvis.household_speaker import speaker_context, shared_knowledge_enabled

ZONE = ZoneInfo('Europe/Oslo')
ACTIVE = {'scheduled', 'failed', 'missed'}


class IsolatedReminderDelivery:
    """Do not share the primary HA websocket's receive stream with reminders."""
    def __init__(self, client, *, factory=None):
        self.client, self.factory = client, factory

    async def call_service(self, domain, service, data):
        if (domain, service) != ('persistent_notification', 'create'):
            raise ValueError('Reminder delivery only creates HA notifications')
        factory = self.factory
        if factory is None:
            from jarvis.homeassistant.client import HomeAssistantClient
            factory = HomeAssistantClient
        reader = factory(self.client.url, self.client.token, self.client.logger)
        try:
            await reader._connect_socket()
            return await reader.call_service(domain, service, data)
        finally:
            await asyncio.wait_for(reader.disconnect(), 2)


def wall_time(day, hour, minute):
    naive = datetime.fromisoformat(day).replace(hour=hour, minute=minute)
    candidates = {naive.replace(tzinfo=ZONE, fold=fold).astimezone(timezone.utc)
                  for fold in (0, 1)
                  if naive.replace(tzinfo=ZONE, fold=fold).astimezone(timezone.utc).astimezone(ZONE).replace(tzinfo=None) == naive}
    if len(candidates) != 1:
        raise ValueError('That Norway clock time is missing or ambiguous because of daylight saving. Please choose another time.')
    return candidates.pop()


def due_time(phrase, now):
    phrase = clean(phrase).casefold()
    phrase = re.sub(r'\ba\.?m\.?\b', 'am', phrase)
    phrase = re.sub(r'\bp\.?m\.?\b', 'pm', phrase)
    reversed_date = re.fullmatch(r'(at .+?) (today|tomorrow|\d{4}-\d{2}-\d{2})', phrase)
    if reversed_date:
        phrase = reversed_date[2] + ' ' + reversed_date[1]
    relative = re.fullmatch(r'in (\d{1,4}) (minutes?|hours?|days?)', phrase)
    if relative:
        amount = int(relative[1])
        seconds = amount * (60 if relative[2].startswith('minute') else 3600 if relative[2].startswith('hour') else 86400)
        due = now.astimezone(timezone.utc) + timedelta(seconds=seconds)
    else:
        match = re.fullmatch(r'(?:(today|tomorrow|(?:next )?(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|\d{4}-\d{2}-\d{2}) )?(?:at )?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', phrase)
        if not match or (match[3] is None and match[4] is None):
            raise ValueError('Please give a precise time, for example tomorrow at 08:00 or in 20 minutes. Times use Europe/Oslo.')
        hour, minute = int(match[2]), int(match[3] or 0)
        if minute > 59 or hour > 23 or (match[4] and not 1 <= hour <= 12):
            raise ValueError('That clock time is invalid. Please use 00:00–23:59 or am/pm.')
        if match[4]:
            hour = hour % 12 + (12 if match[4] == 'pm' else 0)
        day, _ = resolve_dates(match[1] or 'today', now.astimezone(ZONE).date().isoformat())
        due = wall_time(day, hour, minute)
    if not 0 < (due - now.astimezone(timezone.utc)).total_seconds() <= 366 * 86400:
        raise ValueError('Please choose a future time within the next year; I will not silently move a past time to another day.')
    return due


class PersonalReminders:
    def __init__(self, profile, path, client=None, *, now=None, clock=time.monotonic):
        self.profile, self.path, self.client = profile, Path(path), client
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.clock, self.pending, self.lock = clock, OrderedDict(), RLock()
        self.delivery_lock = asyncio.Lock()

    def _load(self):
        if not self.path.exists():
            return {'schema_version': 1, 'revision': 0, 'items': []}
        if self.path.stat().st_size > 524288:
            raise ValueError('Reminder storage needs maintenance; no changes were made.')
        data = json.loads(self.path.read_text(encoding='utf-8'))
        if (data.get('schema_version') != 1 or type(data.get('revision')) is not int
                or not isinstance(data.get('items'), list) or len(data['items']) > 500):
            raise ValueError('Reminder storage needs maintenance; no changes were made.')
        ids = set()
        for row in data['items']:
            if (not isinstance(row, dict) or not re.fullmatch(r'[a-f0-9]{8}', str(row.get('id', '')))
                    or row['id'] in ids or row.get('owner') not in {p['id'] for p in self.profile._data['members']}
                    or row.get('state') not in ACTIVE | {'delivered', 'cancelled', 'completed'}
                    or not isinstance(row.get('text'), str) or not 1 <= len(row['text']) <= 240
                    or type(row.get('attempts')) is not int or not 0 <= row['attempts'] <= 3
                    or datetime.fromisoformat(row['due']).tzinfo is None):
                raise ValueError('Reminder storage needs maintenance; no changes were made.')
            ids.add(row['id'])
        return data

    def _save(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data['revision'] += 1
        fd, name = tempfile.mkstemp(prefix='.reminders-', dir=self.path.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                os.chmod(name, 0o600)
                json.dump(data, f, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(name, self.path)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def _response(self, message, status='success'):
        return {**result(message, status), 'provider': 'personal_reminders'}

    def clear(self, key):
        if key:
            self.pending.pop(str(key), None)

    def handle(self, text, key):
        if not shared_knowledge_enabled(self.profile._data):
            self.clear(key)
            return None
        with self.lock:
            try:
                return self._handle(text, key)
            except Exception:
                self.clear(key)
                return self._response('I could not safely read or save reminders. Nothing is confirmed; please check reminder storage.', 'unavailable')

    def _handle(self, text, key):
        value = re.sub(r'^please ', '', clean(text), flags=re.I)
        lower = value.casefold()
        key = str(key) if key else None
        self.pending = OrderedDict((k, v) for k, v in self.pending.items() if v['expires'] > self.clock())
        pending = self.pending.pop(key, None) if key else None
        hint = speaker_context(self.profile._data)
        if pending and lower in ('no', 'cancel', 'cancel reminder change', 'never mind'):
            return self._response('Cancelled the proposed reminder change. Saved reminders are unchanged.')
        if lower in ('yes', 'yes please', 'confirm reminder') and pending:
            if pending['speaker'] != hint['member_id']:
                return self._response('The speaker changed. Please make the reminder request again; nothing was changed.', 'clarification_required')
            data = self._load()
            if data != pending['before']:
                return self._response('Reminders changed while this confirmation was waiting. Please request the change again.', 'clarification_required')
            if pending['row']['state'] == 'scheduled' and datetime.fromisoformat(pending['row']['due']) <= self.now():
                return self._response('That time has already passed. Please choose a new future time.', 'clarification_required')
            if pending['kind'] == 'create':
                data['items'].append(pending['row'])
            else:
                data['items'] = [pending['row'] if r['id'] == pending['row']['id'] else r for r in data['items']]
            self._save(data)
            return self._response('Saved: ' + self.describe(pending['row']) + '. ' +
                ('Delivery is a Home Assistant notification, not spoken audio or a phone alarm.'
                 if pending['row']['state'] == 'scheduled' else 'Any notification already displayed is not removed by this change.'))
        if lower == 'confirm reminder':
            return self._response('There is no pending reminder change. Please make the request again.', 'clarification_required')
        relevant = bool(re.match(r'(?:remind\b|(?:show|list|what|cancel|delete|complete|reschedule|move|set|create|add|remove)\b.*\breminders?\b)', lower))
        if not relevant:
            return None
        data = self._load()
        members = self.profile._data['members']
        # A task such as "remind me to call Linda" still belongs to the current
        # speaker. Never select ownership from a person's name inside the task.
        if re.match(r'(?:cancel|delete|complete|reschedule|move) my reminder\b', lower):
            named = []
        elif lower.startswith('remind '):
            named = [p for p in members if re.match(r'remind ' + re.escape(p['preferred_name']) + r'\b', value, re.I)]
        else:
            named = [p for p in members if re.search(r'\b' + re.escape(p['preferred_name']) + r"(?:'s)?\b", value, re.I)]
        collective = bool(re.search(r'\b(?:all|household|our) reminders\b', lower))
        own = bool(re.search(r'\b(?:me|my)\b', lower))
        if named and own and not lower.startswith('remind '):
            return self._response('Please choose your reminders or one named person’s reminders, not both in the same request.', 'clarification_required')
        if len(named) > 1:
            return self._response('Please choose one reminder owner.', 'clarification_required')
        owner = named[0]['id'] if named else hint['member_id'] if own else None
        if re.match(r'(show|list|what)\b', lower):
            if not owner and not collective:
                return self._response('Whose reminders should I show? Name a person, or ask for all reminders.', 'clarification_required')
            rows = sorted((r for r in data['items'] if (collective or r['owner'] == owner)
                           and r['state'] != 'cancelled' and r['state'] != 'completed'), key=lambda r: r['due'])
            return self._response(' '.join(self.describe(r) + '.' for r in rows[:20]) +
                                  (' There are more; ask about one person.' if len(rows) > 20 else '')
                                  if rows else 'No saved reminders match that view. This is separate from calendar appointments.')
        mutation = re.fullmatch(r'(cancel|delete|complete) reminder ([a-f0-9]{8})', lower)
        move = re.fullmatch(r'(?:reschedule|move) reminder ([a-f0-9]{8}) (?:to |for )?(.+)', lower)
        # Natural task labels are safe only when they select one exact saved row.
        label_change = re.fullmatch(r'(cancel|delete|complete|reschedule|move) (?:my |' +
            '|'.join(re.escape(p['preferred_name'].casefold()) + r"'s " for p in members) +
            r')reminder (?:to |about )?(.+)', lower)
        if not mutation and not move and label_change:
            verb, label = label_change[1], label_change[2]
            phrase = None
            if verb in ('reschedule', 'move'):
                split = re.fullmatch(r'(.+?) (?:to|for) ((?:today|tomorrow|next |in |at |\d{4}-).+)', label)
                if split:
                    label, phrase = split[1], split[2]
                else:
                    return self._response('Please specify the exact saved task and the new future time.', 'clarification_required')
            choices = [r for r in data['items'] if r['owner'] == owner and r['state'] not in ('completed', 'cancelled')
                       and clean(r['text']).casefold() == label.strip('“”"')]
            if len(choices) != 1:
                return self._response('That task does not select one saved reminder. Please show reminders and use an exact reminder ID.', 'clarification_required')
            identifier = choices[0]['id']
            mutation = re.fullmatch(r'(cancel|delete|complete) reminder ([a-f0-9]{8})', verb + ' reminder ' + identifier)
            if phrase:
                move = re.fullmatch(r'(?:reschedule|move) reminder ([a-f0-9]{8}) (?:to |for )?(.+)', 'move reminder ' + identifier + ' to ' + phrase)
        if mutation or move:
            identifier = mutation[2] if mutation else move[1]
            matches = [r for r in data['items'] if r['id'] == identifier]
            if len(matches) != 1 or matches[0]['state'] in ('completed', 'cancelled'):
                return self._response('I could not find an active reminder with that exact ID.', 'clarification_required')
            row = deepcopy(matches[0])
            if mutation:
                row['state'] = 'completed' if mutation[1] == 'complete' else 'cancelled'
            else:
                try:
                    row['due'] = due_time(move[2], self.now()).isoformat()
                except ValueError as error:
                    return self._response(str(error), 'clarification_required')
                row.update(state='scheduled', attempts=0)
            kind = 'update'
        else:
            if not owner:
                return self._response('Who is this reminder for? Use their name, or ask when your voice is matched.', 'clarification_required')
            # A precise trailing time keeps task contents inert. Also accept time-first wording.
            name = next(p['preferred_name'] for p in members if p['id'] == owner)
            prefix = r'remind (?:me|' + re.escape(name) + r') '
            remainder = re.sub('^' + prefix, '', value, flags=re.I)
            if remainder == value:
                return self._response('Use “remind me to … tomorrow at 08:00”, or name the person.', 'clarification_required')
            split = re.fullmatch(r'to (.+?) ((?:in \d+ (?:minutes?|hours?|days?))|(?:(?:today|tomorrow|(?:next )?(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|\d{4}-\d{2}-\d{2}) )?at .+)', remainder, re.I)
            if split:
                label, phrase = split[1], split[2]
            else:
                split = re.fullmatch(r'(.+?) to (.+)', remainder, re.I)
                if not split:
                    return self._response('Please include the task and an exact future time, for example “remind me tomorrow at 08:00 to check my bag”.', 'clarification_required')
                phrase, label = split[1], split[2]
            if not 1 <= len(label) <= 240 or re.search(r'\b(password|token|secret|api.?key)\b|sk-[\w-]+', label, re.I):
                return self._response('Use a short reminder without passwords or credentials.', 'clarification_required')
            try:
                due = due_time(phrase, self.now())
            except ValueError as error:
                return self._response(str(error), 'clarification_required')
            if len(data['items']) >= 500 or sum(r['state'] in ACTIVE for r in data['items']) >= 200:
                return self._response('Reminder capacity reached; saved reminders need maintenance before adding more.', 'unavailable')
            if any(r['owner'] == owner and r['text'].casefold() == label.casefold() and r['due'] == due.isoformat() and r['state'] in ACTIVE for r in data['items']):
                return self._response('That reminder is already saved; I have not added a duplicate.')
            row = {'id': secrets.token_hex(4), 'owner': owner, 'text': label, 'due': due.isoformat(), 'state': 'scheduled', 'attempts': 0}
            kind = 'create'
        if not key:
            return self._response('Please use an ongoing conversation so I can safely confirm this reminder.', 'clarification_required')
        self.pending[key] = {'before': data, 'row': row, 'kind': kind, 'speaker': hint['member_id'], 'expires': self.clock() + 300}
        while len(self.pending) > 100:
            self.pending.popitem(last=False)
        return self._response('Proposed: ' + self.describe(row) + '. ' +
            ('Delivery will be a Home Assistant notification, not spoken audio or a phone alarm. ' if row['state'] == 'scheduled' else '') +
            'Reply yes or “confirm reminder” to save, or no to discard.', 'clarification_required')

    def describe(self, row):
        name = next(p['preferred_name'] for p in self.profile._data['members'] if p['id'] == row['owner'])
        due = datetime.fromisoformat(row['due']).astimezone(ZONE)
        return f"Reminder {row['id']} for {name}: “{row['text']}”, {due:%A %d %B %Y at %H:%M %Z}, {row['state']}"

    def upcoming(self, owner, start, end):
        with self.lock:
            return [deepcopy(r) for r in self._load()['items'] if (owner == 'all' or r['owner'] == owner)
                    and r['state'] in ACTIVE | {'delivered'} and start <= datetime.fromisoformat(r['due']) < end]

    async def deliver_due(self):
        if not self.client or not shared_knowledge_enabled(self.profile._data):
            return
        async with self.delivery_lock:
            with self.lock:
                candidates = [deepcopy(r) for r in self._load()['items'] if r['state'] == 'scheduled'
                              and datetime.fromisoformat(r['due']) <= self.now()][:10]
            for row in candidates:
                # Claim attempt durably before sending. Stable notification_id makes
                # an uncertain retry/restart update the same HA notification.
                with self.lock:
                    data = self._load()
                    current = next((r for r in data['items'] if r['id'] == row['id']), None)
                    if current != row:
                        continue
                    if self.now() - datetime.fromisoformat(row['due']) > timedelta(days=7):
                        current['state'] = 'missed'
                        self._save(data)
                        continue
                    if current['attempts'] >= 3:
                        current['state'] = 'failed'
                        self._save(data)
                        continue
                    current['attempts'] += 1
                    self._save(data)
                    claimed = deepcopy(current)
                try:
                    await asyncio.wait_for(self.client.call_service('persistent_notification', 'create', {
                        'title': 'Jarvis reminder', 'message': self.describe(claimed),
                        'notification_id': 'jarvis_reminder_' + row['id']}), 10)
                    success = True
                except Exception:
                    success = False
                with self.lock:
                    data = self._load()
                    current = next((r for r in data['items'] if r['id'] == row['id']), None)
                    if current != claimed:
                        continue
                    if success:
                        current['state'] = 'delivered'
                    elif current['attempts'] >= 3:
                        current['state'] = 'failed'
                    self._save(data)

    async def run(self):
        while True:
            try:
                await self.deliver_due()
            except Exception:
                # Corrupt/unreadable storage is never reset or marked delivered.
                pass
            await asyncio.sleep(30)
