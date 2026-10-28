"""Calendar arithmetic and attributed insights for a local language model.

These are calendar constraints, not conclusions about actual attendance or free
time. Never execute calendar text. No profile writes, model calls or tool access.
"""
from collections import defaultdict
from datetime import datetime, timedelta
import re
from zoneinfo import ZoneInfo

ZONE = ZoneInfo('Europe/Oslo')


def purpose(question, previous=None):
    value = question.casefold()
    for goal, pattern in (
        ('availability', r'\b(fit|free|available|time for|room for|squeeze|spare time)\b'),
        ('conflicts', r'\b(overlap|clash|conflict|double.book)\w*\b'),
        ('busyness', r'\b(busy|busier|busiest|packed|stressful|hectic|manageable|full)\b'),
        ('preparation', r'\b(prepare|preparation|ready|bring)\b'),
        ('priorities', r'\b(important|matters?|focus|priorit\w*|attention)\b'),
    ):
        if re.search(pattern, value):return goal
    if previous and (re.match(r'^(and|what about|how about)\b', value) or duration_minutes(value) is not None):return previous
    return 'overview'


def duration_minutes(question):
    value=question.casefold().strip(' .?!')
    if re.fullmatch(r'(?:about |around )?(?:half an hour|a half hour)',value):return 30
    match=re.search(r'(?<![\d.])(\d{1,3}(?:\.\d{1,2})?)[ -]?(minute|min|hour)\w*\b',value)
    if not match:return None
    minutes=float(match[1])*(60 if match[2]=='hour' else 1)
    return (int(minutes) if minutes.is_integer() else minutes) if 0<minutes<=720 else None


def activity(title):
    """Conservative localisation of explicit calendar vocabulary, not inference.

    Unknown names stay quoted as data. A rehearsal doesn't establish instrument,
    a training entry doesn't establish sport, and no label assigns transport.
    """
    lower = title.casefold()
    if re.search(r'ignore\b.*\b(instruction|rule)|system prompt|api.?key|password|\bunlocked?\b|return.*json', lower):
        return 'appointment with an unclear title'
    if re.search(r'\bkorps\w*', lower) and re.search(r'øving|øvelse|rehearsal|practice', lower):return 'band rehearsal'
    if re.search(r'\btannlege\w*', lower):return 'dentist appointment'
    if re.search(r'\bforeldremøte\w*', lower):return 'parents’ meeting'
    if re.search(r'\butviklingssamtale\w*', lower):return 'school progress meeting'
    if re.search(r'\bfotball\w*', lower) and re.search(r'trening|økt|practice', lower):return 'football practice'
    if re.search(r'\bsvømme\w*', lower) and re.search(r'trening|kurs|practice', lower):return 'swimming session'
    if re.search(r'\btrening\b', lower):return 'training session (sport not specified)'
    return title



def appointment_label(fact):
    """Use only the exact person/calendar/title meaning attached by the reader."""
    meaning=fact.get('confirmed_activity')
    if isinstance(meaning,dict):
        from jarvis.household_activities import title_key
        from jarvis.preparation_wording import activity_name
        if (fact.get('owners')==[meaning.get('person')] and fact.get('source')==meaning.get('source')
                and title_key(fact['text'])==title_key(meaning.get('title','')) and meaning.get('id')):
            return activity_name(meaning['activity'])
    return activity(fact['text'])


def _union_minutes(intervals):
    end = None;total = 0
    for start, stop in sorted(intervals):
        start = max(start, end) if end is not None else start
        total += max(0, stop-start)/60
        end = max(end or stop, stop)
    return int(total)


def insights(evidence, question, speaker, goal=None):
    """Derive a small reasoning board; all claims retain source fact IDs."""
    goal = goal or purpose(question)
    people = evidence['people']
    appointments = [f for f in evidence['facts'] if f['kind']=='appointment']
    routines = [f for f in evidence['facts'] if f['kind']=='routine']
    overlaps = [f for f in evidence['facts'] if f['kind']=='overlap']
    prepared=[];by_day=defaultdict(list)
    for fact in appointments:
        title = appointment_label(fact)
        owner = ' and '.join(people[p] for p in fact['owners'])
        start, end = datetime.fromisoformat(fact['start']), datetime.fromisoformat(fact['end'])
        stamp = fact['date_label']+(' (all-day entry)' if fact['all_day'] else ' '+fact['local_start']+'–'+fact['local_end'])
        prepared.append({'id':fact['id'], 'owner':owner, 'event':title, 'when':stamp})
        if not fact['all_day']:
            day = start.astimezone(ZONE).replace(hour=0,minute=0,second=0,microsecond=0)
            while day.timestamp()<end.timestamp():
                stop=day+timedelta(days=1)
                for person in fact['owners']:
                    by_day[(person, day.date().isoformat())].append((fact,max(start.timestamp(),day.timestamp()),min(end.timestamp(),stop.timestamp())))
                day=stop
    days=[]
    for (owner, date), rows in sorted(by_day.items()):
        minutes=_union_minutes([(a,b) for _,a,b in rows])
        days.append({'owner':people[owner], 'date':date,
            'timed_entries':len(rows),'scheduled_minutes_without_double_counting':minutes,
            'scheduled_hours_without_double_counting':minutes/60,
            'calendar_load_assessment':('relatively light' if minutes<=120 else 'moderate' if minutes<=240 else 'substantial')+' recorded appointment load, not a judgment of the whole day',
            'basis':'returned timed calendar entries only; excludes routines and unrecorded commitments',
            'evidence':[r[0]['id'] for r in rows]})
    focus = 'Summarise the shape of this period, highlighting specific commitments rather than reciting all sources.'
    if goal=='preparation':
        focus='Lead with the extra appointment(s) to plan around, then one relevant conditional preparation check. Do not let usual school/work crowd out specific commitments.'
    elif goal=='busyness':
        focus='Assess calendar load tentatively using occupied minutes, spread and overlaps. Say based on the appointments, not that this proves the whole day is busy or free.'
    elif goal=='availability':
        focus='Explain the recorded time constraint. If duration is missing, ask how long the proposed activity should take. Do not equate a calendar gap with actual availability.'
    elif goal=='conflicts':
        focus='Distinguish a same-person double booking from different people having events at the same time. For the latter, whether it is a practical clash depends on shared responsibilities; do not assume them. Only same-person overlaps might be duplicates/updates.'
    elif goal=='priorities':
        focus='Highlight concrete commitments or overlaps worth attention. Do not invent urgency or rank one family member above another.'
    duration=duration_minutes(question)
    activity_requested=bool(re.search(r'\b(fit|squeeze|time for|room for|(?:free|available) for)\b',question,re.I) or duration is not None)
    parallel=[]
    timed=[f for f in appointments if not f['all_day']]
    for index,a in enumerate(timed):
        for b in timed[index+1:]:
            if a['owners']==b['owners']:continue
            if datetime.fromisoformat(a['start']).timestamp()<datetime.fromisoformat(b['end']).timestamp() and datetime.fromisoformat(b['start']).timestamp()<datetime.fromisoformat(a['end']).timestamp():
                parallel.append({'people':[people[a['owners'][0]],people[b['owners'][0]]],
                    'events':[appointment_label(a),appointment_label(b)],
                    'relationship':'Coincide in clock time for different people, not an individual double booking. Practical conflict depends on responsibilities that are not known.',
                    'evidence':[a['id'],b['id']]})
    relations=[]
    for routine in routines:
        clocks=re.search(r'\bschool\b.*?(\d{2}:\d{2})[–-](\d{2}:\d{2})',routine['text'],re.I)
        if not clocks:continue
        for appointment in appointments:
            if appointment['all_day'] or appointment['owners']!=routine['owners'] or appointment['date'] not in routine.get('dates',[]):continue
            if appointment['local_start']>=clocks[2]:
                relations.append({'owner':people[appointment['owners'][0]],'event':appointment_label(appointment),
                    'usual_school_finish':clocks[2], 'appointment_start':appointment['local_start'],
                    'relationship':'later than usual school finish, not overlapping that timetable; what happens in between is not known',
                    'evidence':[routine['id'],appointment['id']]})
    gaps=[]
    window=evidence.get('window','all_day')
    if goal=='availability' and duration and len(people)==1 and window!='all_day' and not evidence['source_failures'] and not evidence['truncated']:
        first=evidence.get('start')
        last=evidence.get('end_exclusive')
        if first and last:
            day=datetime.fromisoformat(first).replace(tzinfo=ZONE)
            a,b={'morning':(6,12),'afternoon':(12,18),'evening':(18,24)}[window]
            while day.date().isoformat()<last:
                begin,stop=((day+timedelta(hours=h)).timestamp() for h in (a,b))
                for owner in people:
                    owned=[f for f in appointments if owner in f['owners'] and datetime.fromisoformat(f['start']).timestamp()<stop and datetime.fromisoformat(f['end']).timestamp()>begin]
                    if any(f['all_day'] for f in owned):continue
                    intervals=sorted((max(begin,datetime.fromisoformat(f['start']).timestamp()),min(stop,datetime.fromisoformat(f['end']).timestamp())) for f in owned)
                    cursor=begin
                    for start,end in intervals+[(stop,stop)]:
                        if start-cursor>=duration*60:
                            gaps.append({'owner':people[owner],'date':day.date().isoformat(),
                                'start':datetime.fromtimestamp(cursor,ZONE).strftime('%H:%M'),
                                'end':datetime.fromtimestamp(start,ZONE).strftime('%H:%M'),
                                'basis':'Gap in returned calendar entries only, NOT confirmed availability.'})
                        cursor=max(cursor,end)
                day+=timedelta(days=1)
    missing_duration=goal=='availability' and activity_requested and duration is None
    missing_window=goal=='availability' and activity_requested and duration is not None and window=='all_day'
    board={'purpose':goal,'answer_the_question':focus,
        'speaking_to':people.get(speaker, speaker) if speaker else 'unidentified household member',
        'appointments':prepared[:12], 'calendar_load':days[:14] if goal!='availability' else [],
        'potential_same_person_conflicts':[{'text':f['text'],'when':f['date_label']+' '+f['local_start']+'–'+f['local_end'],'evidence':[f['id']]} for f in overlaps],
        'no_same_person_timed_overlap_found':not bool(overlaps),
        'different_person_parallel_commitments':parallel[:4],
        'timetable_relationships':relations[:8],
        'usual_routines':[{'id':f['id'],'owner':[people[p] for p in f['owners']], 'text':f['text'], 'dates':f.get('dates',[])} for f in routines[:4]],
        'requested_activity_duration_minutes':duration,
        'duration_clarification_needed':missing_duration,
        'window_clarification_needed':missing_window,
        'required_question':'How long would you like it to take?' if missing_duration else 'Which part of the day are you thinking of?' if missing_window else None,
        'candidate_calendar_gaps':gaps[:6],
        'empty_view_statement':'No entries returned from the connected calendars; that does not establish an empty day.' if not appointments and not evidence['source_failures'] else None,
        'coverage':'Incomplete: calendars are not proof of attendance or free time.',
        'missing_sources':evidence['source_failures'],
        'limited_view':evidence['truncated'] or len(prepared)>12 or len(days)>14 or len(routines)>4}
    if evidence.get('between_requested') and goal=='availability':
        between=[]
        for owner in people:
            owned=sorted((f for f in appointments if owner in f['owners'] and not f['all_day']),key=lambda f:f['start'])
            for first,second in zip(owned,owned[1:]):
                stop=datetime.fromisoformat(first['end']);start=datetime.fromisoformat(second['start'])
                if stop.date()!=start.date() or start<=stop:continue
                if any(owner in f['owners'] and f['all_day'] and datetime.fromisoformat(f['start'])<start and datetime.fromisoformat(f['end'])>stop for f in appointments):continue
                between.append({'owner':people[owner],'date':start.date().isoformat(),'start':stop.strftime('%H:%M'),'end':start.strftime('%H:%M'),
                    'calendar_gap_minutes':int((start.timestamp()-stop.timestamp())/60),
                    'between':[appointment_label(first),appointment_label(second)],
                    'basis':'Between these recorded appointments only; not confirmed free time, travel time or dinner availability.'})
        board['between_appointment_gaps']=between[:6]
        board['duration_clarification_needed']=len(between)==1 and duration is None
        board['window_clarification_needed']=False
        board['required_question']=('Which two appointments do you mean?' if len(between)!=1 else
            'How long would you like it to take?' if duration is None else None)
        board['candidate_calendar_gaps']=between if len(between)==1 and (duration is None or duration<=between[0]['calendar_gap_minutes']) and not evidence['truncated'] and not evidence['source_failures'] else []
        board['answer_the_question']='Use the recorded interval between the prior appointments. Do not invent an event duration, journey time or availability. The gap length is NOT the proposed dinner duration. Ask the required question if the pair/duration is unclear.'
        if not speaker:board['answer_the_question']+=' No speaker is identified: name the calendar owner, not you/your/we/us. Explain the gap in that person\'s calendar, not the speaker\'s availability.'
        if len(between)==1 and duration is not None:
            board['requested_minutes_fit_recorded_gap']=duration<=between[0]['calendar_gap_minutes']
    return board



def relative_day(start,reference):
    if not reference:return None
    day=datetime.fromisoformat(start).date();today=datetime.fromisoformat(reference).date()
    delta=(day-today).days
    return 'today' if delta==0 else 'tomorrow' if delta==1 else day.strftime('%A') if 0<=delta<7 else day.strftime('%A %d %B')


def day_overview(board,evidence):
    """Small, complete input for conversational one-person/one-day answers."""
    if (board['purpose']!='overview' or len(evidence['people'])!=1 or board['limited_view'] or
        board['missing_sources'] or len(board['appointments'])>4 or
        (datetime.fromisoformat(evidence['end_exclusive'])-datetime.fromisoformat(evidence['start'])).days!=1):return None
    by_id={f['id']:f for f in evidence['facts'] if f['kind']=='appointment'}
    entries=[]
    for entry in board['appointments']:
        fact=by_id[entry['id']]
        if not fact['all_day'] and datetime.fromisoformat(fact['start']).date()!=datetime.fromisoformat(fact['end']).date():return None
        entries.append({'id':entry['id'],'owner':entry['owner'],'event':entry['event'],
            'start':None if fact['all_day'] else fact['local_start'],
            'end':None if fact['all_day'] else fact['local_end'],'all_day':fact['all_day']})
    school=[]
    if not entries:
        for routine in board['usual_routines']:
            match=re.search(r'usual school.*?(\d{2}:\d{2})\s*[–-]\s*(\d{2}:\d{2})',routine['text'],re.I)
            if match:school.append({'owners':routine['owner'],'start':match[1],'finish':match[2],'basis':'usual timetable,not confirmed attendance'})
    return {'day':relative_day(evidence['start'],evidence.get('checked_on')) or evidence['start'],
        'appointments':entries,'usual_school':school,'usual_routines':board['usual_routines'] if not entries and not school else [],
        'empty_calendar_scope':'No appointments were returned from the connected household calendar for this day; this is not proof of actual availability.' if not entries else None}


def grounded_reply(board, speaker_name):
    """Natural conclusions from computed relationships if neural wording fails.

    This is explicitly a calculated recovery, not a claim that a rejected model
    answer passed. No unknown logistics, title interpretation or free-time claims.
    Return None where the evidence cannot support a useful conclusion.
    """
    if board['missing_sources'] or board['limited_view']:return None
    goal=board['purpose']
    def possessive(name):return 'Your' if name==speaker_name else name+'’s'
    def within(name):return 'your' if name==speaker_name else name+'’s'
    def whose(name):return 'you' if name==speaker_name else name
    appointments=board['appointments']
    if goal=='overview' and board.get('day_overview') and 1<len(appointments)<=4:
        brief=board['day_overview'];grouped={}
        for item in brief['appointments']:grouped.setdefault(item['owner'],[]).append(item)
        pieces=[]
        for owner,events in grouped.items():
            subject='you' if owner==speaker_name else owner
            clauses=[e['event']+(' as an all-day entry' if e['all_day'] else ' at '+e['start']) for e in events]
            joined=clauses[0]+', then '+', then '.join(clauses[1:]) if len(clauses)>1 else clauses[0]
            pieces.append(((brief['day'][:1].upper()+brief['day'][1:]) if brief['day'] in ('today','tomorrow') else 'On '+brief['day'])+', '+subject+(' have ' if owner==speaker_name or ' and ' in owner else ' has ')+joined+'.')
            if events[-1]['end']:pieces.append('The last appointment finishes at '+events[-1]['end']+'.')
        answer=' '.join(pieces)
        return answer if len(answer.split())<=100 else None
    if goal=='overview' and 1<len(appointments)<=4:
        # A complete small overview must not become a single-event relationship.
        grouped={}
        for item in appointments:grouped.setdefault(item['owner'],[]).append(item['event']+' on '+item['when'])
        pieces=[]
        for owner,entries in grouped.items():
            who='You' if owner==speaker_name else owner
            verb='have' if owner==speaker_name or ' and ' in owner else 'has'
            joined=entries[0]+' and '+entries[1] if len(entries)==2 else ', '.join(entries[:-1])+', and '+entries[-1] if len(entries)>2 else entries[0]
            pieces.append(who+' '+verb+' '+joined+'.')
        answer=' '.join(pieces)
        return answer if len(answer.split())<=100 else None
    if goal=='conflicts':
        conflicts=board['potential_same_person_conflicts']
        if conflicts:
            return 'There’s a possible double booking at '+conflicts[0]['when']+'. It’s worth checking whether both entries still apply before deciding to move either.'
        parallel=board['different_person_parallel_commitments']
        if parallel:
            a,b=parallel[0]['people']
            return possessive(a)+' and '+within(b)+' events coincide, but that isn’t a double booking for one person. Whether it’s a practical clash depends on who needs to be involved—will you need to coordinate both?'
    if goal=='availability' and appointments:
        between=board.get('between_appointment_gaps',[])
        if len(between)==1 and board.get('requested_minutes_fit_recorded_gap') is False:
            gap=between[0]
            return 'The recorded gap is '+gap['start']+'–'+gap['end']+', only '+str(gap['calendar_gap_minutes'])+' minutes. A '+str(board['requested_activity_duration_minutes'])+'-minute activity does not fit inside that calendar interval; travel and other commitments are still unknown.'
        entry=appointments[0]
        constraint=possessive(entry['owner'])+' '+entry['event']+' is scheduled for '+entry['when']+'.'
        if len(between)==1:
            gap=between[0]
            constraint=possessive(gap['owner'])+' calendar has a '+str(gap['calendar_gap_minutes'])+'-minute gap, '+gap['start']+'–'+gap['end']+', between '+gap['between'][0]+' and '+gap['between'][1]+'.'
        if board['required_question']:return constraint+' '+board['required_question']
        if board['candidate_calendar_gaps']:
            gap=board['candidate_calendar_gaps'][0]
            return 'A '+str(board['requested_activity_duration_minutes'])+'-minute activity could fit within the '+gap['start']+'–'+gap['end']+' gap in '+within(gap['owner'])+' calendar. Using that calendar option is conditional on your other commitments.'
    if goal=='busyness' and board['calendar_load']:
        load=max(board['calendar_load'],key=lambda row:row['scheduled_minutes_without_double_counting'])
        minutes=load['scheduled_minutes_without_double_counting']
        label='manageable' if minutes<=120 else 'moderate' if minutes<=240 else 'substantial'
        duration=f'{minutes/60:g} hours' if minutes%60==0 else str(minutes)+' minutes'
        day=datetime.fromisoformat(load['date']).strftime('%A %d %B')
        lead=(day+' looks busiest for '+whose(load['owner'])+' among these calendar entries' if len(board['calendar_load'])>1 else possessive(load['owner'])+' scheduled appointments look '+label)
        return lead+', with '+duration+' booked. That’s a view of the appointments, not a measure of the whole day’s workload.'
    if goal in ('overview','preparation','priorities') and board['timetable_relationships']:
        relation=board['timetable_relationships'][0]
        appointment=next((a for a in appointments if a['event']==relation['event'] and a['owner']==relation['owner']),None)
        if appointment:
            return 'The extra thing to plan around is '+within(relation['owner'])+' '+relation['event']+' on '+appointment['when']+'. It’s later than '+within(relation['owner'])+' usual school finish at '+relation['usual_school_finish']+', rather than a clash with that timetable.'
    return None


def routine_with_empty_calendar(evidence, speaker):
    """Verified one-day recovery; no returned events never means available."""
    if evidence['source_failures'] or evidence['truncated'] or len(evidence['people'])!=1:return None
    if (datetime.fromisoformat(evidence['end_exclusive'])-datetime.fromisoformat(evidence['start'])).days!=1:return None
    coverage=[f for f in evidence['facts'] if f['kind']=='coverage']
    if not coverage or any(f['returned_entries']!=0 for f in coverage):return None
    person=next(iter(evidence['people']));name=evidence['people'][person]
    label=relative_day(evidence['start'],evidence.get('checked_on'))
    prefix=(((label[:1].upper()+label[1:]) if label in ('today','tomorrow') else 'On '+label)+', ') if label else ''
    subject='you' if person==speaker else name
    lead=''
    for fact in evidence['facts']:
        if fact['kind']!='routine' or person not in fact['owners']:continue
        match=re.search(r'usual school.*?(\d{2}:\d{2})\s*[–-]\s*(\d{2}:\d{2})',fact['text'],re.I)
        if match:
            lead=prefix+subject+(' usually finish' if person==speaker else ' usually finishes')+' school at '+match[2]+'. '
            break
        if re.search(r'no school.*usual weekend',fact['text'],re.I):
            lead=('You have' if person==speaker else name+' has')+' no school in the usual weekend routine. '
            break
    return lead+"I don't see anything extra in the connected household calendar"+(' for '+label if label and not lead else ' for that day' if not lead else '')+'.'


def routine_with_calendar_gap(evidence, speaker):
    """Useful confirmed routine when a personal calendar was never connected."""
    if len(evidence['people'])!=1 or not any('no connected personal calendar' in reason for reason in evidence['source_failures']):return None
    person=next(iter(evidence['people']))
    name=evidence['people'][person]
    who='You usually' if person==speaker else name+' usually'
    for fact in evidence['facts']:
        if fact['kind']!='routine' or person not in fact['owners']:continue
        match=re.search(r'leave for work around\s*(\d{2}:\d{2}).*?finish around\s*(\d{2}:\d{2})',fact['text'],re.I)
        if match:
            verb='leave' if person==speaker else 'leaves'
            finish='finish' if person==speaker else 'finishes'
            return who+' '+verb+' for work around '+match[1]+' and '+finish+' around '+match[2]+'. I can use that routine for planning, but the personal calendar isn’t connected, so extra appointments remain unknown.'
    return None
