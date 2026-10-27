"""Conversational wording of approved planning facts, without another model call.

Only presentation lives here. Dates, access, calendar reads, and view selection
remain with the planning handlers. Calendar text is always quoted as data.
"""
from datetime import date, timedelta
import re


def join_words(values):
    values = list(values)
    if len(values) < 2:
        return ''.join(values)
    return ', '.join(values[:-1]) + ' and ' + values[-1]


def date_words(value):
    day = date.fromisoformat(value)
    return day.strftime('%A ') + str(day.day) + day.strftime(' %B')


def on_dates(values, reference):
    days = sorted(set(values))
    if len(days) == 1:
        label = date_words(days[0])
        offset = (date.fromisoformat(days[0]) - date.fromisoformat(reference)).days
        if offset in (0, 1):
            return ('today' if offset == 0 else 'tomorrow') + ' (' + label + ')'
        return 'on ' + label
    first, last = date.fromisoformat(days[0]), date.fromisoformat(days[-1])
    if (last - first).days + 1 == len(days):
        return 'from ' + date_words(days[0]) + ' to ' + date_words(days[-1])
    return 'on ' + join_words(date_words(day) for day in days)


def quote(value):
    # Quote the title itself, including text that resembles instructions.
    return '“' + value.removeprefix('“').removesuffix('”') + '”'


def render_groups(groups, *, focus='overview', reference, more=False):
    """Speak card groups as connected facts, keeping unknowns and exceptions."""
    sentences, caveats = [], set()
    empty_calendar, unavailable_calendar, weekends, unknown_stays = {}, {}, {}, []
    # Appointments lead a plans answer; routine metadata must not crowd them out.
    ordered = sorted(groups.items(), key=lambda item: 0 if item[0][0].endswith(' · familiekalender') else 1)
    for (title, raw_lines), dates in ordered:
        lines = [line.removeprefix('“').removesuffix('”') for line in raw_lines]
        name, _, kind = title.partition(' · ')
        when = on_dates(dates, reference)
        if kind == 'familiekalender':
            events = []
            for line in lines:
                if line.startswith('No entries returned'):
                    empty_calendar.setdefault(name, []).extend(dates)
                elif line.startswith(('Calendar unavailable', 'Calendar is not enabled')):
                    unavailable_calendar.setdefault(name, []).extend(dates)
                elif re.match(r'\d+ (?:additional|more) ', line):
                    events.append(line)
                else:
                    label, separator, event = line.partition(' · ')
                    if separator:
                        if label == 'All day':
                            events.append(quote(event) + ' (all day)')
                        elif label.startswith('Ongoing from '):
                            events.append(quote(event) + ' (' + label.lower() + ')')
                        else:
                            # Household answers already use Norway local time.
                            events.append(quote(event) + ' at ' + re.sub(r' (?:CEST|CET)$', '', label))
                    else:
                        events.append(quote(line))
            if events:
                sentences.append(name + (' have ' if ' & ' in name else ' has ') + join_words(events) + ' in the family calendar ' + when + '.')
        elif kind == 'usual school':
            hours = re.fullmatch(r'(\d{2}:\d{2})–(\d{2}:\d{2})', lines[0])
            finish = re.fullmatch(r'Usual school finish: (\d{2}:\d{2})\.', lines[0])
            if focus == 'school_end' and (hours or finish):
                end = hours[2] if hours else finish[1]
                sentences.append(name + ' usually finishes school at ' + end + ' ' + when + '.')
            elif hours:
                sentences.append(name + "'s usual school hours are " + hours[1] + '–' + hours[2] + ' ' + when + '.')
            else:
                sentences.append('I don’t have ' + name + "'s school hours recorded " + when + '.')
            caveats.add('school')
        elif kind == 'school' and lines[0].startswith('No school in the usual weekend'):
            weekends.setdefault(tuple(dates), []).append(name)
        elif kind == 'confirmed exception':
            sentences.append(name + ' has a confirmed household update for no school ' + when + '.')
        elif kind == 'usual work':
            hours = re.search(r'(\d{2}:\d{2}).*finish around (\d{2}:\d{2})', lines[0])
            if hours:
                if focus == 'work_finish':
                    sentences.append(name + ' usually finishes work around ' + hours[2] + ' ' + when + '.')
                else:
                    sentences.append(name + ' usually leaves for work around ' + hours[1] + ' and finishes around ' + hours[2] + ' ' + when + '.')
                caveats.add('work')
            else:
                sentences.append('For ' + name + ' ' + when + ': ' + ' '.join(lines))
        elif kind == 'usual bus':
            bus = re.search(r'\d{2}:\d{2}', lines[0])
            if bus:
                sentences.append(name + "'s usual bus is around " + bus[0] + ' ' + when + ', when he is staying here.')
                caveats.add('bus')
            else:
                sentences.append('For ' + name + ' ' + when + ': ' + ' '.join(lines))
        elif kind == 'reported stay':
            if lines[0] == 'Reported staying here':
                sentences.append(name + ' is reported as staying here ' + when + ', based on a manual report rather than live location.')
            elif lines[0] == 'Reported staying with Mum':
                sentences.append(name + ' is reported as staying with Mum ' + when + ', based on a manual report rather than live location.')
            else:
                unknown_stays.append(name + "'s stay is not confirmed " + when + '.')
        elif kind == 'after school':
            if lines[0].startswith('No school in the usual weekend'):
                sentences.append(name + ' doesn’t usually have school ' + when + ', so there isn’t an after-school window for that day.')
            elif lines[0].startswith('No school-finish time'):
                sentences.append('I don’t have a school finish time for ' + name + ' ' + when + ', so I cannot define an after-school window.')
            elif lines[0].startswith('No approved shared'):
                sentences.append('I don’t have shared after-school hours and a calendar for ' + name + ' ' + when + '.')
            elif lines[0].startswith('Family calendar unavailable'):
                sentences.append('I can’t read ' + name + "'s family calendar " + when + ', so those plans are unknown.')
            else:
                events = []
                finish = next((match[1] for line in lines
                               if (match := re.match(r'Based on the usual (\d{2}:\d{2}) school finish', line))), None)
                school_finish = 'the usual ' + (finish + ' ' if finish else '') + 'school finish'
                for line in lines:
                    match = re.fullmatch(r'(\d{2}:\d{2}–\d{2}:\d{2}) · (.+)', line)
                    if match:
                        events.append(quote(match[2]) + ' (' + match[1] + ')')
                    elif line.startswith('No timed family-calendar'):
                        sentences.append('I don’t see any timed appointments for ' + name + ' after ' + school_finish + ' ' + when + '. Plans outside the family calendar may still exist.')
                    elif line.startswith('There are all-day'):
                        sentences.append('There are also all-day entries for ' + name + '; I can’t assign those an after-school time.')
                    elif line.startswith('Additional timed'):
                        sentences.append('There are more appointments; open the calendar for all the details.')
                    elif line.startswith('Based on the usual'):
                        caveats.add('school')
                if events:
                    sentences.append(name + ' has ' + join_words(events) + ' after ' + school_finish + ' ' + when + '.')
        elif title == 'Usual household routine':
            wake = next((line.partition(': ')[2] for line in lines if line.startswith('Wake time: ')), None)
            beds = [line.replace(' bedtime: ', ' at ') for line in lines if ' bedtime: ' in line]
            routine = ('getting up at ' + wake) if wake else ''
            if beds:
                routine += (' and ' if routine else '') + 'bedtime for ' + join_words(beds)
            sentences.append('The usual household routine ' + when + ' is ' + (routine or ' '.join(lines)) + '.')
        elif title == 'Weekend routine':
            sentences.append('There are no fixed weekend wake-up or bedtime hours ' + when + '.' if lines[0].startswith('No fixed wake-up or bedtime') else 'The weekend routine ' + when + ' is: ' + ' '.join(lines))
        elif title == 'Birthday':
            sentences.append(' '.join(lines).replace('today', when).replace('on this date', when))
        else:
            sentences.append('For ' + name + ' ' + when + ': ' + ' '.join(lines))

    for dates, names in weekends.items():
        sentences.append(join_words(names) + (' has' if len(names) == 1 else ' have') + ' no school in the usual weekend routine ' + on_dates(dates, reference) + '.')
    for name, dates in unavailable_calendar.items():
        sentences.append('I can’t read ' + name + "'s family calendar " + on_dates(dates, reference) + ', so those appointments are unknown.')
    # In a wider overview, empty calendar days are lower priority than plans.
    # They remain explicit in a personal/calendar answer and in expanded detail.
    if focus == 'calendar' or more or not any('in the family calendar' in s for s in sentences):
        for name, dates in empty_calendar.items():
            sentences.append('I don’t see any appointments in ' + name + "'s family calendar " + on_dates(dates, reference) + '. Plans outside that calendar may still exist.')
    if focus == 'stay' or more or not sentences:
        sentences.extend(unknown_stays)
    elif unknown_stays:
        sentences.append('I don’t have confirmed plans for Emrik’s stay for the whole period.')
    limit = 60 if more else 12
    omitted = len(sentences) > limit
    sentences = sentences[:limit]
    if 'school' in caveats:
        sentences.append('That’s the usual school timetable; holidays and actual attendance are not verified.')
    if 'work' in caveats or 'bus' in caveats:
        routines = 'Work and bus times' if {'work', 'bus'} <= caveats else ('Work times' if 'work' in caveats else 'Bus times')
        sentences.append(routines + ' are usual routines; actual attendance' + (' and bus service are' if 'bus' in caveats else ' is') + ' not confirmed.')
    if omitted:
        sentences.append('There’s more to cover; say “tell me more” or ask about a particular day.')
    if len(sentences) > 4:
        # Read a weekly answer as appointments followed by routine/context prose.
        last_event = max((i for i, sentence in enumerate(sentences)
                          if 'in the family calendar' in sentence), default=-1)
        if 0 <= last_event < len(sentences)-1:
            return ' '.join(sentences[:last_event+1]) + '\n\n' + ' '.join(sentences[last_event+1:])
    return ' '.join(sentences) or 'I don’t have any shared plans recorded for that period.'
