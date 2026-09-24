"""Read-only, deterministic Mia calendar answers; no event text goes to a model."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import re


class HouseholdCalendar:
    def __init__(self, profile, client, allowed_entities, *, clock=None):
        self.profile, self.client = profile, client
        self.allowed = frozenset(allowed_entities)
        self.zone = ZoneInfo('Europe/Oslo')
        self.clock = clock or (lambda: datetime.now(self.zone))

    @staticmethod
    def result(message, status='success'):
        return {'status': status, 'message': message, 'provider': 'household_calendar', 'cacheable': False}

    async def handle(self, text):
        value = ' '.join(text.casefold().strip(' .?!').split())
        if not re.search(r'\b(mia|familiekalender)\b', value):
            return None
        # Usual school hours are profile facts, not calendar-event requests.
        if re.search(r'\b(usual|usually|normally)\b', value) and 'familiekalender' not in value and 'calendar' not in value:
            return None
        if not re.search(r'\b(calendar|schedule|appointments?|activities|plans|doing|on|planned|familiekalender)\b', value):
            return None
        if not re.match(r'^(what|when|which|does|is|has|show|read|tell|any)\b', value):
            return self.result('This calendar connection is read-only. No events were changed.', 'clarification_required')
        context = self.profile.context().get('approved_personal_details', {}).get('Mia', {})
        entity = context.get('calendar', {}).get('ha_entity_id')
        if entity != 'calendar.familiekalender' or entity not in self.allowed:
            return self.result("Mia's calendar is not enabled for this assistant.", 'unavailable')
        now = self.clock().astimezone(self.zone)
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if 'tomorrow' in value:
            start, end, label = midnight + timedelta(days=1), midnight + timedelta(days=2), 'tomorrow'
        elif 'today' in value:
            start, end, label = midnight, midnight + timedelta(days=1), 'today'
        elif 'next week' in value:
            start = midnight + timedelta(days=7-midnight.weekday())
            end, label = start + timedelta(days=7), 'next week'
        elif 'this week' in value:
            start = midnight - timedelta(days=midnight.weekday())
            end, label = start + timedelta(days=7), 'this week'
        elif re.search(r'\b(next|upcoming)\b', value) and not re.search(r'\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday|month|year)\b', value):
            start, end, label = now, now + timedelta(days=30), 'in the next 30 days'
        else:
            return self.result("Should I check Mia's calendar for today, tomorrow, this week, next week, or her next appointment?", 'clarification_required')
        try:
            response = await self.client.call_service_response('calendar', 'get_events', {
                'entity_id': entity, 'start_date_time': start.isoformat(), 'end_date_time': end.isoformat()})
            events = response[entity]['events']
            if not isinstance(events, list):
                raise ValueError('Missing event list')
            entries = []
            for event in events:
                raw = event['start']
                if isinstance(raw, dict):
                    raw = raw.get('dateTime') or raw.get('date')
                if len(raw) == 10:
                    dt = datetime.fromisoformat(raw).replace(tzinfo=self.zone)
                    stamp = dt.strftime('%A %d %B') + ', all day'
                else:
                    dt = datetime.fromisoformat(raw.replace('Z', '+00:00'))
                    if dt.tzinfo is None:
                        raise ValueError('Ambiguous event timezone')
                    dt = dt.astimezone(self.zone)
                    stamp = dt.strftime('%A %d %B at %H:%M')
                title = ' '.join(str(event.get('summary') or 'Untitled appointment').split())[:160]
                entries.append((dt, f'{stamp}: {title}'))
            entries.sort(key=lambda item: item[0])
        except Exception:
            return self.result("I couldn't read Mia's calendar reliably just now. That does not mean she has no plans.", 'unavailable')
        if not entries:
            return self.result(f"No entries were returned from Mia's familiekalender {label}. Her usual school routine is separate, and the calendar may not contain all her plans.")
        limit = 1 if label == 'in the next 30 days' else 6
        answer = f"Mia's calendar {label}, in Norway local time: " + '; '.join(item[1] for item in entries[:limit]) + '.'
        if len(entries) > limit:
            answer += f' There are {len(entries)-limit} more entries in that period.'
        return self.result(answer)
