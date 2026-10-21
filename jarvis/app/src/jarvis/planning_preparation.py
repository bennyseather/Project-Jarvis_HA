"""On-demand preparation grounded in fresh approved sources, not inferred plans."""
import asyncio
from collections import OrderedDict
from datetime import datetime, timedelta
import math
import re
import time
from zoneinfo import ZoneInfo

from jarvis.household_briefing import HouseholdBriefing, Brief
from jarvis.household_memory import clean, result
from jarvis.household_planning import resolve_dates, Plan
from jarvis.household_speaker import speaker_context, shared_knowledge_enabled

ZONE = ZoneInfo('Europe/Oslo')


class PlanningPreparation:
    def __init__(self, profile, client, registry, allowed, *, reminders=None, travel=None,
                 now=None, clock=time.monotonic):
        self.profile, self.client, self.registry = profile, client, registry
        self.allowed, self.reminders, self.travel = frozenset(allowed), reminders, travel
        self.now = now or (lambda: datetime.now(ZONE))
        self.clock, self.sessions = clock, OrderedDict()
        self.briefings = HouseholdBriefing(profile, client, allowed, now=self.now, clock=clock)

    def clear(self, key):
        if key:
            self.sessions.pop(str(key), None)

    def request(self, text, key):
        value = re.sub(r'^(?:please |jarvis[, ]+)+', '', clean(text).casefold())
        hint = speaker_context(self.profile._data)
        previous = self.sessions.pop(str(key), None) if key else None
        reference = self.now().astimezone(ZONE).date().isoformat()
        same = (previous and previous['speaker'] == hint['member_id'] and previous['expires'] > self.clock()
                and previous['revision'] == self.profile._data['revision'] and previous['date'] == reference
                and previous.get('start'))
        follow = bool(re.fullmatch(r'(?:and|what about|how about) (?:tomorrow|today|next week|this week|this weekend|next weekend|the following week|(?:next )?(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday))', value))
        travel = bool(re.fullmatch(r'(?:help me prepare for|what should i prepare for|how should i prepare for) (?:my |the )?next (?:trip|journey|flight|travel)', value))
        preparation = bool(re.fullmatch(r'(?:what (?:should|do) (?:i|we|\w+) (?:need to )?(?:prepare|prepare for|get ready for)|'
            r'help (?:me|us) (?:prepare|prepare for|plan)|how should (?:i|we) prepare)(?: .+)?', value))
        if not (preparation or travel or (same and follow)):
            return None
        # No action under a read-only planning prefix.
        if re.search(r'\b(turn|unlock|buy|pay|send|book|cancel|delete|set|remind|remember)\b', value):
            return None
        if same and follow:
            subject = previous['subject']
        else:
            names = [p['id'] for p in self.profile._data['members'] if re.search(r'\b' + re.escape(p['preferred_name']) + r'\b', value, re.I)]
            if len(names) > 1:
                raise ValueError('Please ask about one person, or the household.')
            collective = bool(re.search(r'\b(we|us|household|family)\b', value))
            subject = names[0] if names else 'all' if collective else hint['member_id']
        if not subject:
            raise ValueError('Whose preparation should I check? Name a person, or ask when your voice is matched.')
        if travel:
            return subject, None, None, True
        # Don't mistake an unsupported date/destination for today's home plan.
        date_text = (re.sub(r'^(?:and|what about|how about) ', '', value) if same and follow else
                     re.sub(r'\b(?:what|should|do|i|we|need|to|prepare|for|get|ready|help|me|us|plan|how)\b', '', value))
        for p in self.profile._data['members']:
            date_text = re.sub(r'\b' + re.escape(p['preferred_name']) + r'\b', '', date_text, flags=re.I)
        date_text = ' '.join(date_text.split())
        if not re.fullmatch(r'(?:today|tomorrow|day after tomorrow|this week|next week|this weekend|next weekend|the following week|'
                            r'(?:next )?(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|\d{4}-\d{2}-\d{2})?', date_text):
            raise ValueError('Please choose a day, weekend, week, or ask about your next trip. I will not guess the time or destination.')
        prior = Plan((subject,), 'overview', previous['start'], previous['end']) if same and follow else None
        start, end = resolve_dates(value if same and follow else date_text, reference, prior)
        return subject, start, end, False

    async def handle(self, text, key):
        if not shared_knowledge_enabled(self.profile._data):
            return None
        try:
            request = self.request(text, key)
        except ValueError as error:
            return self.response(str(error), 'clarification_required')
        if request is None:
            return None
        subject, start, end, trip = request
        hint = speaker_context(self.profile._data)
        revision = self.profile._data['revision']
        reference = self.now().astimezone(ZONE).date().isoformat()
        marker = {'subject': subject, 'speaker': hint['member_id'], 'expires': self.clock() + 300,
                  'revision': revision, 'date': reference, 'start': start, 'end': end}
        if key:
            self.sessions[str(key)] = marker
            while len(self.sessions) > 100:
                self.sessions.popitem(last=False)
        def changed():
            return (revision != self.profile._data['revision'] or not shared_knowledge_enabled(self.profile._data)
                    or reference != self.now().astimezone(ZONE).date().isoformat()
                    or (key and self.sessions.get(str(key)) is not marker))
        if trip:
            if subject != 'benny' or self.travel is None:
                return self.response('I do not have a connected travel calendar for that person; I cannot build a verified trip plan.', 'unavailable')
            approval = self.profile._data.get('sharing_policy', {}).get('additional_category_approval', {})
            if not (approval.get('source') and approval.get('recorded_on') and 'benny_travel_details' in approval.get('categories', [])):
                return self.response('Travel details are not shared for this preparation view.', 'unavailable')
            try:
                travel = await asyncio.wait_for(self.travel.handle('When is my next travel?', conversation_id=None), 15)
            except Exception:
                travel = None
            if changed():
                return self.response('That preparation check was superseded or its context changed. Please ask again.', 'unavailable')
            if not travel or travel.get('status') != 'success':
                return self.response('I could not reliably read the travel calendar. Your next trip is unknown, not absent.', 'unavailable')
            return self.response(travel['message'] + ' General preparation suggestions, not verified requirements: check your current booking, travel documents and the carrier’s luggage rules. '
                'I have not checked destination weather. I have not calculated when to leave home; that needs the departure airport, transport plan and check-in allowance. No reminder or booking was created.')
        briefing, weather = await asyncio.gather(self.briefings.handle('preparation', None,
                                                   resolved=Brief(subject, start, end)), self.weather(start, end))
        if changed():
            return self.response('That preparation check was superseded or its context changed. Please ask again.', 'unavailable')
        if briefing is None or briefing.get('status') != 'success':
            return self.response('I could not build a reliable planning summary. Please ask again.', 'unavailable')
        lines = [briefing['message'], weather]
        if self.reminders is not None:
            try:
                a, b = (datetime.fromisoformat(x).replace(tzinfo=ZONE) for x in (start, end))
                reminders = self.reminders.upcoming(subject, a, b)
                if reminders:
                    lines.append('Saved reminders: ' + '; '.join(self.reminders.describe(r) for r in reminders[:5]) + '.')
                    if len(reminders) > 5:
                        lines.append('More saved reminders exist; ask to show reminders for the full list.')
                else:
                    lines.append('No saved reminders fall in that period; this is separate from calendar plans.')
            except Exception:
                lines.append('Reminder storage could not be read; reminders are unknown, not empty.')
        lines.append('Preparation suggestions: check any appointment details and unresolved overlaps above. '
                     'School and work routines do not confirm attendance or who is doing transport. '
                     'I have not created reminders, changed appointments, or operated devices.')
        return {**self.response(' '.join(lines)), 'read_only': True, 'period': {'start': start, 'end': end}}

    @staticmethod
    def response(message, status='success'):
        return {**result(message, status), 'provider': 'planning_preparation'}

    async def weather(self, start, end):
        entities = [e for e in self.registry.all() if e.domain == 'weather' and e.entity_id in self.allowed] if self.registry else []
        if not entities:
            return 'No home weather source is connected or shared; I have not guessed the forecast.'
        preferred = next((e for e in entities if e.entity_id == 'weather.forecast_home'), entities[0])
        try:
            raw = await asyncio.wait_for(self.client.call_service_response('weather', 'get_forecasts', {
                'entity_id': preferred.entity_id, 'type': 'daily'}), 8)
            items = raw[preferred.entity_id]['forecast']
            if not isinstance(items, list) or len(items) > 32:
                raise ValueError()
            forecasts = {}
            for item in items:
                stamp = datetime.fromisoformat(item['datetime'].replace('Z', '+00:00'))
                if stamp.tzinfo is None:
                    raise ValueError()
                date = stamp.astimezone(ZONE).date().isoformat()
                if start <= date < end:
                    if date in forecasts:
                        raise ValueError()
                    forecasts[date] = item
            if not forecasts:
                return 'The home forecast does not cover the requested dates; destination weather has not been checked.'
            conditions = {'rainy': 'rain', 'pouring': 'heavy rain', 'snowy': 'snow', 'snowy-rainy': 'rain and snow',
                          'sunny': 'sun', 'partlycloudy': 'some cloud', 'cloudy': 'cloud', 'fog': 'fog',
                          'windy': 'wind', 'windy-variant': 'wind', 'lightning': 'thunderstorms', 'lightning-rainy': 'thunderstorms and rain',
                          'clear-night': 'clear weather', 'exceptional': 'exceptional conditions'}
            lines = []
            wet = False
            for day, item in sorted(forecasts.items())[:3]:
                condition = conditions.get(item.get('condition'), 'unspecified conditions')
                probability = item.get('precipitation_probability')
                valid_probability = isinstance(probability, (int, float)) and not isinstance(probability, bool) and math.isfinite(probability) and 0 <= probability <= 100
                stamp = datetime.fromisoformat(day).strftime('%A %d %B')
                lines.append(stamp + ': ' + condition + (f', {probability:g}% chance of precipitation' if valid_probability else ''))
                wet |= item.get('condition') in ('rainy', 'pouring', 'snowy', 'snowy-rainy', 'lightning-rainy') or (valid_probability and probability >= 60)
            coverage = (datetime.fromisoformat(end) - datetime.fromisoformat(start)).days
            message = 'Home-area forecast, not destination weather: ' + '; '.join(lines) + '.'
            if len(forecasts) < coverage or len(forecasts) > 3:
                message += ' Only the displayed dates are covered here; I have not filled missing days from old forecasts.'
            if wet:
                message += ' Consider rain protection if you will be outside; I do not know whether your activities are outdoors.'
            return message
        except Exception:
            return 'The home forecast is temporarily unavailable; I have not reused an old forecast or guessed destination weather.'
