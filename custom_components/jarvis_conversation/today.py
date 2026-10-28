"""Deterministic read-only day view from an already shared profile projection."""
import json
import asyncio
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

ZONE = ZoneInfo('Europe/Oslo')
DAYS = ('monday','tuesday','wednesday','thursday','friday','saturday','sunday')

def build_today(data, now=None, stay=None):
    now = (now or datetime.now(ZONE)).astimezone(ZONE)
    day, date = DAYS[now.weekday()], now.date().isoformat()
    cards = []
    def add(title, *lines): cards.append({'title':title, 'lines':list(lines)})
    overrides = data.get('exceptions', [])
    for person in data.get('profiles', []):
        name, details = person['name'], person.get('details', {})
        try:
            birthday = datetime.fromisoformat(details.get('birth_date','')).date()
            if (birthday.month,birthday.day)==(now.month,now.day): add('Birthday',name+' has a birthday today.')
        except (ValueError,TypeError): pass
        school=details.get('school', {})
        bus=details.get('school_routine', {})
        exception=any(r.get('person')==name.casefold() and r.get('kind')=='no_school' and r.get('on')==date for r in overrides)
        if exception: add(name+' · confirmed exception','No school today (confirmed household update).')
        elif school or bus:
            if now.weekday()>=5: add(name+' · school','No school in the usual weekend routine.')
            elif school:
                hours=next((h for h in school.get('weekly_hours',[]) if h.get('day')==day),None)
                add(name+' · usual school',f"{hours['start']}–{hours['end']}" if hours else 'Hours not recorded for today.', 'Term dates/holidays and attendance are not confirmed.')
            elif day in bus.get('days',[]):
                add(name+' · usual bus',f"Around {bus.get('bus_departure','time not recorded')}, only when staying here.", 'Service and attendance are not confirmed.')
        work=details.get('work_routine',{})
        if day in work.get('work_days',[]):
            finish=next((r['value'] for r in overrides if r.get('person')==name.casefold() and r.get('kind')=='work_finish' and r.get('on')==day),work.get('usual_work_finish','not recorded'))
            add(name+' · usual work',f"Leave for work around {work.get('usual_departure_for_work','not recorded')}; finish around {finish}.", 'Not work start or arrival home; actual attendance unknown.')
    routines=data.get('routines',{})
    if day in routines.get('weekdays',[]):
        add('Usual household routine','Wake time: '+routines.get('usual_wake_time','not recorded'), *[f'{name.title()} bedtime: {time}' for name,time in routines.get('bedtimes',{}).items()])
    elif routines.get('weekend_policy') and now.weekday()>=5: add('Weekend routine',routines['weekend_policy'])
    if any(p['name']=='Emrik' and p.get('details',{}).get('school_routine') for p in data.get('profiles',[])):
        label='Not confirmed'
        try:
            record=json.loads(stay or '')
            until=record.get('until')
            end=datetime.fromisoformat(until.replace('Z','+00:00')) if until else None
            if end and (end.tzinfo is None or end<=now): raise ValueError()
            label={'here':'Reported staying here','mum':'Reported staying with Mum','unknown':'Not confirmed'}[record['state']]
        except (ValueError,TypeError,KeyError,AttributeError): pass
        add('Emrik · reported stay',label,'Manual report, not live location. No presence inferred for anyone else.')
    return {'date':date,'timezone':'Europe/Oslo','cards':cards}

PERIODS = ('today','tomorrow','week_ahead','this_week','next_week','custom')

def period_bounds(period, now, start_date=None, end_date=None):
    start=now.astimezone(ZONE).replace(hour=0,minute=0,second=0,microsecond=0)
    if period=='custom':
        import re
        if not all(isinstance(v,str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}',v) for v in (start_date,end_date)):
            raise ValueError('Custom period requires ISO dates')
        a,b=date.fromisoformat(start_date),date.fromisoformat(end_date)
        if not start.date()<=a<=start.date()+timedelta(days=366) or not 1<=(b-a).days<=14 or b>start.date()+timedelta(days=367):
            raise ValueError('Custom period must contain 1 to 14 future days within the next year')
        return datetime.combine(a,datetime.min.time(),ZONE),datetime.combine(b,datetime.min.time(),ZONE)
    if start_date is not None or end_date is not None: raise ValueError('Dates require custom period')
    if period=='today': end=start+timedelta(days=1)
    elif period=='tomorrow': start+=timedelta(days=1);end=start+timedelta(days=1)
    elif period=='week_ahead': end=start+timedelta(days=7)
    elif period=='this_week': end=start+timedelta(days=7-start.weekday())
    elif period=='next_week': start+=timedelta(days=7-start.weekday());end=start+timedelta(days=7)
    else: raise ValueError('Unsupported household period')
    return start,end

def event_interval(event):
    def stamp(raw):
        if isinstance(raw,dict):raw=raw.get('dateTime') or raw.get('date')
        if not isinstance(raw,str):raise ValueError('Missing event date')
        all_day=len(raw)==10
        dt=datetime.fromisoformat(raw.replace('Z','+00:00'))
        if all_day:dt=dt.replace(tzinfo=ZONE)
        if dt.tzinfo is None:raise ValueError('Ambiguous event timezone')
        return dt.astimezone(ZONE),all_day
    start,all_day=stamp(event['start']);end,end_all_day=stamp(event['end'])
    if end.timestamp()<=start.timestamp() or end_all_day!=all_day:raise ValueError('Invalid event interval')
    title=' '.join(str(event.get('summary') or 'Untitled appointment').split())[:160]
    return start,end,all_day,title

async def add_period(hass, data, period='today', *, now=None, start_date=None, end_date=None):
    now=(now or datetime.now(ZONE)).astimezone(ZONE)
    start,end=period_bounds(period,now,start_date,end_date)
    state=hass.states.get('input_text.jarvis_emrik_stay')
    details=next((p.get('details',{}) for p in data.get('profiles',[]) if p['name']=='Mia'),{})
    calendar=details.get('calendar',{}).get('ha_entity_id')
    error='Calendar is not enabled for shared access.'
    entries=[]
    if calendar=='calendar.familiekalender':
        try:
            planner=data.get('planner',{})
            if planner.get('ready') and any(k.startswith('uid:') for k in planner.get('assignments',{})):
                from homeassistant.components.calendar import DATA_COMPONENT
                entity=hass.data[DATA_COMPONENT].get_entity(calendar)
                source=await asyncio.wait_for(entity.async_get_events(hass,start,end),8)
                events=[{**e.as_dict(),'start':e.start.isoformat(),'end':e.end.isoformat(),'uid':e.uid,'recurrence_id':e.recurrence_id} for e in source]
            else:
                response=await asyncio.wait_for(hass.services.async_call('calendar','get_events',{'entity_id':calendar,'start_date_time':start.isoformat(),'end_date_time':end.isoformat()},blocking=True,return_response=True),8)
                events=response[calendar]['events']
            if not isinstance(events,list) or len(events)>500: raise ValueError('Unbounded or invalid calendar response')
            for event in events:
                if event.get('status')=='cancelled':continue
                planner=data.get('planner',{})
                if planner.get('ready'):
                    from .planner_membership import assignment
                    meta=assignment(event,{p['id'] for p in planner['members']},planner.get('assignments',{}),True)
                    entries.append((*event_interval(event),meta['members']))
                else:entries.append((*event_interval(event),['mia']))
            entries.sort(key=lambda row:(row[0],row[3]));error=None
        except Exception: error='Calendar unavailable. Plans are unknown, not empty.';entries=[]
    days=[]
    for offset in range((end.date()-start.date()).days):
        day=start+timedelta(days=offset);day_end=day+timedelta(days=1)
        current=day.date()==now.date()
        result=build_today(data,now if current else day,state.state if current and state else None)
        if not current:
            for card in result['cards']:
                card['lines']=[line.replace('for today','for this date').replace('today','on this date') for line in card['lines']]
                if card['title']=='Emrik · reported stay':
                    card['lines']=['Future stay not confirmed.','A current stay report is not a confirmed plan for this date.']
        lines=[]
        daily_events=[]
        owner_lines={}
        for event_start,event_end,all_day,title,owners in entries:
            if event_start.timestamp()>=day_end.timestamp() or event_end.timestamp()<=day.timestamp():continue
            label='All day' if all_day else (event_start.strftime('%H:%M %Z') if event_start.timestamp()>=day.timestamp() else 'Ongoing from '+event_start.strftime('%d %b %H:%M %Z'))
            lines.append(label+' · '+title)
            owner_lines.setdefault(tuple(owners),[]).append(label+' · '+title)
            row={'start':event_start.isoformat(),'end':event_end.isoformat(),'all_day':all_day,'title':title}
            if data.get('planner',{}).get('ready'):row['owners']=owners
            daily_events.append(row)
        total=len(lines)
        lines=([error] if error else lines[:20])
        if total>20 and not error:lines.append(f'{total-20} additional entries; open the calendar.')
        if not lines:lines=['No entries returned for this date. This does not mean no plans.']
        if data.get('planner',{}).get('ready'):
            names={p['id']:p['name'] for p in data['planner']['members']}
            for owners,items in owner_lines.items():
                label=' & '.join(names[p] for p in owners) if owners else 'Unassigned'
                result['cards'].append({'title':label+' · familiekalender','owners':list(owners),'lines':items[:20]})
            if error:result['cards'].append({'title':'Household · familiekalender','lines':[error]})
        else:result['cards'].append({'title':'Mia · familiekalender','lines':lines})
        result['calendar']={'status':'available' if error is None else ('not_shared' if calendar!='calendar.familiekalender' else 'unavailable'),
                            'events':daily_events if error is None else []}
        result['cards'].append({'title':'Today · '+result['date'] if current else 'Date · '+result['date'],
            'lines':['Norway local date; usual routines plus confirmed exceptions.','Calendar entries are plans, not attendance. No devices or events changed.']})
        days.append(result)
    data['planning']={'period':period,'start_date':start.date().isoformat(),'end_date_exclusive':end.date().isoformat(),
                      'generated_on':now.date().isoformat(),'timezone':'Europe/Oslo','days':days}
    if period=='today':data['today']=days[0]
    return data

async def add_today(hass,data):
    return await add_period(hass,data,'today')
