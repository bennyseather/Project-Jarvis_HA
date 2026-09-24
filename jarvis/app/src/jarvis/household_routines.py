"""Bounded, confirmed routine overrides; never attendance or device actions."""
from datetime import date, datetime, timedelta
import re
from zoneinfo import ZoneInfo

ZONE = ZoneInfo('Europe/Oslo')
DAYS = ('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday')


def today():
    return datetime.now(ZONE).date()


def allowed(document, category):
    approval = document.get('sharing_policy', {}).get('additional_category_approval', {})
    return bool(approval.get('source') and approval.get('recorded_on') and category in approval.get('categories', []))


def validate(records):
    if not isinstance(records, list) or len(records) > 100:
        raise ValueError('Routine override limit')
    keys = set()
    for r in records:
        if not isinstance(r, dict) or set(r) != {'person', 'kind', 'on', 'value'}:
            raise ValueError('Invalid routine record')
        if r['kind'] == 'work_finish':
            if r['person'] != 'linda' or r['on'] not in DAYS or not isinstance(r['value'], str) or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', r['value']):
                raise ValueError('Invalid work routine')
        elif r['kind'] == 'no_school':
            if r['person'] not in ('mia', 'emrik') or r['value'] is not True or not isinstance(r['on'], str) or date.fromisoformat(r['on']).isoformat() != r['on']:
                raise ValueError('Invalid school exception')
        else:
            raise ValueError('Unknown routine kind')
        key = (r['person'], r['kind'], r['on'])
        if key in keys:
            raise ValueError('Duplicate routine override')
        keys.add(key)


def resolve_date(value):
    if value in ('today', 'tomorrow'):
        return today() + timedelta(days=value == 'tomorrow')
    return date.fromisoformat(value)


def proposal(text):
    """None means not an edit; errors never become a misleading shared note."""
    value = ' '.join(text.casefold().strip(' .!?').split())
    value = re.sub(r'^(?:remember|save|note)\s+(?:that\s+)?', '', value)
    value = re.sub(r'\bevery (' + '|'.join(DAYS) + r')$', lambda m: 'on ' + m[1] + 's', value)
    work = re.fullmatch(r'linda (?:finishes(?: work)?|ends work) at (\d{1,2}:\d{2}) (?:on |every )?(' + '|'.join(DAYS) + r')s', value)
    school = re.fullmatch(r'(mia|emrik) (?:has no school|does not have school|doesn\x27t have school) (?:on )?(today|tomorrow|\d{4}-\d{2}-\d{2})', value)
    if work:
        stamp = work[1].zfill(5)
        if not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', stamp):
            raise ValueError('Please use a valid 24-hour time, for example 15:00.')
        return {'person': 'linda', 'kind': 'work_finish', 'on': work[2], 'value': stamp}
    if school:
        try:
            day = resolve_date(school[2])
        except ValueError:
            raise ValueError('Please use a valid date in YYYY-MM-DD format.') from None
        if not today() <= day <= today() + timedelta(days=366):
            raise ValueError('Please choose today or a date within the next year.')
        return {'person': school[1], 'kind': 'no_school', 'on': day.isoformat(), 'value': True}
    if re.match(r'^linda (?:finishes|ends work)\b', value) or re.match(r'^(mia|emrik) (?:has no school|does not have school|doesn\x27t have school)\b', value):
        raise ValueError("Please specify a recurring day, such as 'Linda finishes work at 15:00 on Fridays', or an exact exception, such as 'Mia has no school tomorrow'. Nothing was proposed.")
    return None


def category(record):
    return 'work_schedules' if record['kind'] == 'work_finish' else 'school_schedules'


def describe(record):
    if record['kind'] == 'work_finish':
        return f"Linda's usual work finish on {record['on'].title()}s becomes {record['value']} in Norway local time; other weekdays stay unchanged"
    return f"{record['person'].title()} has no school on {record['on']} only (Norway date); this exception expires at the following midnight and does not change the normal weekly routine"


def install(document, record):
    if not allowed(document, category(record)):
        raise ValueError('Sharing this schedule category is not enabled.')
    records = document.setdefault('routine_overrides', [])
    records[:] = [r for r in records if (r['person'], r['kind'], r['on']) != (record['person'], record['kind'], record['on'])]
    records.append(record)
    validate(records)


def active(document):
    return [dict(r) for r in document.get('routine_overrides', [])
            if allowed(document, category(r)) and (r['kind'] != 'no_school' or r['on'] >= today().isoformat())]


def answer(document, text):
    value = ' '.join(text.casefold().strip(' .?!').split())
    # Full matches deliberately leave travel/calendar/general dialogue untouched.
    work = re.fullmatch(r'(?:when|what time) does linda (?:finish(?: work)?|end work) (?:on )?(today|tomorrow|' + '|'.join(DAYS) + r'|\d{4}-\d{2}-\d{2})s?', value)
    school = re.fullmatch(r'(?:does (mia|emrik) have school|is (mia|emrik) (?:at|going to) school) (?:on )?(today|tomorrow|\d{4}-\d{2}-\d{2})', value)
    if work and allowed(document, 'work_schedules'):
        try:
            day = work[1] if work[1] in DAYS else DAYS[resolve_date(work[1]).weekday()]
        except ValueError:
            return result('Please specify a valid date.', 'clarification_required')
        override = next((r for r in active(document) if r['kind'] == 'work_finish' and r['on'] == day), None)
        if override:
            return result(f"Linda usually finishes work at {override['value']} on {day.title()}s, in Norway local time. This is her routine, not confirmation of today's attendance or arrival home.")
        person = next((p for p in document['members'] if p['id'] == 'linda'), {})
        routine = person.get('work_routine', {})
        if routine.get('status') == 'confirmed' and day in routine.get('work_days', []) and routine.get('usual_work_finish'):
            return result(f"Linda's usual work finish is around {routine['usual_work_finish']} on {day.title()}s. This is a routine, not verified attendance or arrival home.")
        return result(f"I have no work-finish time recorded for Linda on {day.title()}s.")
    if school and allowed(document, 'school_schedules'):
        try:
            day = resolve_date(school[3])
        except ValueError:
            return result('Please specify a valid date.', 'clarification_required')
        name = school[1] or school[2]
        exception = next((r for r in document.get('routine_overrides', []) if r['person'] == name and r['kind'] == 'no_school' and r['on'] == day.isoformat()), None)
        if exception:
            return result(f"{name.title()} has no school scheduled on {day.isoformat()}, according to the confirmed household exception. This does not tell me their current location.")
        if day.weekday() >= 5:
            return result(f"{name.title()} has no school scheduled on {day.isoformat()}; it is {DAYS[day.weekday()].title()} in Norway.")
        return result(f"{name.title()}'s normal routine includes school on {DAYS[day.weekday()].title()}s. I have no confirmed no-school exception for {day.isoformat()}, but holidays and actual attendance are not verified.")
    return None


def result(message, status='success'):
    return {'status': status, 'message': message, 'provider': 'household_routines', 'cacheable': False}
