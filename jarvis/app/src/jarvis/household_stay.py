"""Explicit Emrik stay helper. Expiry is evaluated on every read, not inferred presence."""
import asyncio
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import json
import re
import time

ENTITY = 'input_text.jarvis_emrik_stay'
LABELS = {'here': 'Staying here', 'mum': 'Staying with Mum', 'unknown': 'Not confirmed'}


def effective_stay(raw, now=None):
    now = now or datetime.now(timezone.utc)
    try:
        value = json.loads(raw)
        state = value['state']
        if state not in LABELS:
            raise ValueError()
        until = value.get('until')
        if until:
            end = datetime.fromisoformat(until.replace('Z', '+00:00'))
            if end.tzinfo is None:
                raise ValueError()
            if end <= now:
                return 'unknown', None
        return state, until
    except (ValueError, TypeError, KeyError, AttributeError):
        return 'unknown', None


class HouseholdStay:
    def __init__(self, client, profile, *, clock=None):
        self.client, self.profile = client, profile
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.pending = {}
        self.lock = asyncio.Lock()

    @staticmethod
    def result(message, status='success'):
        return {'status': status, 'message': message, 'cacheable': False, 'provider': 'household_stay'}

    async def read(self):
        states = await self.client.get_states()
        entity = next((s for s in states if s.get('entity_id') == ENTITY), None)
        if not entity or entity['state'] in ('unavailable', 'unknown'):
            raise RuntimeError('Stay helper unavailable')
        return entity['state']

    async def handle(self, text, conversation_id):
        async with self.lock:
            return await self._handle(text, conversation_id)

    async def _handle(self, text, conversation_id):
        value = ' '.join(text.casefold().strip(' .?!').split()).replace('’', "'")
        confirmation = value == 'confirm emrik stay'
        cancel = value == 'cancel emrik stay'
        change = re.fullmatch(r"(?:emrik is |set emrik(?:'s)? stay to )(staying here|here|staying with mum|with mum|not confirmed)(?: until (.+))?", value)
        query = re.search(r'\bemrik\b', value) and re.search(r'\b(stay|staying|mum|bus)\b', value)
        if not (confirmation or cancel or change or query):
            return None
        if self.profile._data.get('conversational_updates', {}).get('mode') != 'shared_confirmation':
            return self.result('Shared stay updates are not enabled.', 'unavailable')
        self.pending = {k: p for k, p in self.pending.items() if p['expires'] > time.monotonic()}
        key = str(conversation_id) if conversation_id else None
        if cancel:
            self.pending.pop(key, None)
            return self.result('Emrik stay change cancelled.')
        try:
            raw = await self.read()
        except Exception:
            return self.result("I couldn't read Emrik's reported stay. Nothing was changed.", 'unavailable')
        if confirmation:
            proposal = self.pending.pop(key, None)
            if not proposal:
                return self.result('There is no pending Emrik stay change in this conversation.', 'clarification_required')
            if raw != proposal['before']:
                return self.result('The stay was changed elsewhere. Please repeat your choice.', 'clarification_required')
            record = proposal['record']
            if record['until'] and datetime.fromisoformat(record['until']) <= self.clock():
                return self.result('That expiry has already passed. Please choose a future time.', 'clarification_required')
            try:
                await self.client.call_service('input_text', 'set_value', {'entity_id': ENTITY, 'value': json.dumps(record)})
                if json.loads(await self.read()) != record:
                    raise RuntimeError('Readback mismatch')
            except Exception:
                return self.result('The stay update could not be verified. Check the Yoga selector before retrying.', 'unavailable')
            return self.result(f"Emrik's reported stay is now {LABELS[record['state']]}. " +
                (f"It expires at {record['until']} and then becomes Not confirmed." if record['until'] else 'No expiry is set.') +
                ' No alarms or reminders were enabled.')
        if change:
            if not key:
                return self.result('Use a continuing conversation to confirm the stay change.', 'clarification_required')
            choice = change.group(1)
            state = 'unknown' if choice == 'not confirmed' else 'mum' if 'mum' in choice else 'here'
            until = None
            if change.group(2) and state != 'unknown':
                try:
                    naive = datetime.strptime(change.group(2), '%Y-%m-%d %H:%M')
                    end = naive.replace(tzinfo=ZoneInfo('Europe/Oslo'))
                    if end.utcoffset() != end.replace(fold=1).utcoffset() or end <= self.clock():
                        raise ValueError()
                    until = end.isoformat()
                except ValueError:
                    return self.result('Please give a future unambiguous expiry as YYYY-MM-DD HH:MM, in Norway time, or omit the expiry.', 'clarification_required')
            record = {'state': state, 'until': until}
            if len(self.pending) >= 100:
                self.pending.pop(next(iter(self.pending)))
            self.pending[key] = {'record': record, 'before': raw, 'expires': time.monotonic()+300}
            return self.result(f"Set Emrik to {LABELS[state]}" + (f' until {until}' if until else ', without expiry') +
                ". Say 'confirm Emrik stay' or 'cancel Emrik stay'.", 'clarification_required')
        state, until = effective_stay(raw, self.clock())
        message = f"Emrik's reported stay is {LABELS[state]}. This is a manual household setting, not live location tracking."
        if 'bus' in value:
            if state == 'mum':
                message += " The bus routine for this household does not apply while he is reported as staying with Mum."
            else:
                message += " His usual weekday bus is around 07:40 when staying here; the actual service and school holidays still need checking."
        if until:
            message += f' This setting expires at {until}.'
        return self.result(message)
