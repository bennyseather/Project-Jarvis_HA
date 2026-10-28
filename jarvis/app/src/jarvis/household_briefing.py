"""Fresh speaker-aware briefings from confirmed household/live calendar data.

No model pass, new permission, notification, device action or persistent store.
Calendar titles are quoted data and never used as executable instructions.
"""
import asyncio
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timedelta
import re
import time
from zoneinfo import ZoneInfo

from jarvis.household_memory import clean, result, response_style
from jarvis.household_planning import resolve_dates, Plan, render, validate_range, DATE_PATTERN
from jarvis.household_speaker import shared_knowledge_enabled, speaker_context

ZONE=ZoneInfo('Europe/Oslo')
SOURCES={'family':'calendar.familiekalender','work':'calendar.work_reach','travel':'calendar.jarvis_travels'}


@dataclass(frozen=True)
class Brief:
    subject: str
    start: str
    end: str
    upcoming: bool=False
    more: bool=False


def interval(event, *, event_context=False):
    def stamp(raw):
        if isinstance(raw,dict):raw=raw.get('dateTime') or raw.get('date')
        if not isinstance(raw,str):raise ValueError('Missing event time')
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}',raw):return datetime.fromisoformat(raw).replace(tzinfo=ZONE),True
        dt=datetime.fromisoformat(raw.replace('Z','+00:00'))
        if dt.tzinfo is None:raise ValueError('Ambiguous event time')
        return dt.astimezone(ZONE),False
    start,all_day=stamp(event.get('start'));end,last_day=stamp(event.get('end'))
    if all_day!=last_day or end.timestamp()<=start.timestamp():raise ValueError('Invalid event interval')
    row={'start':start,'end':end,'all_day':all_day,
         'title':clean(event.get('summary') or event.get('title') or 'Untitled appointment')[:180]}
    if event_context:
        from jarvis.event_preparation import source_text
        # Explicit opt-in: ordinary calendar/weather reasoning keeps its accepted
        # compact contract. Descriptions are untrusted data, never instructions.
        row.update(location=source_text(event.get('location'),180),
                   description=source_text(event.get('description'),900))
    return row


def event_title(event):
    """Use established exact airport mappings, never guessed city names."""
    from jarvis.homeassistant.travel_calendar_intelligence import TravelCalendarIntelligence as Travel
    route=Travel._route({'summary':event['title']})
    if route:
        a,b=route
        return Travel._AIRPORT_CITIES.get(a,a)+' to '+Travel._AIRPORT_CITIES.get(b,b)
    return event['title']


class HouseholdBriefing:
    def __init__(self, profile, client, allowed_entities=(), *, now=None, clock=time.monotonic, reminders=None):
        self.profile,self.client,self.allowed=profile,client,frozenset(allowed_entities)
        self.now=now or (lambda:datetime.now(ZONE))
        self.clock,self.sessions=clock,OrderedDict()
        self.reminders=reminders

    def clear(self,key):
        if key:self.sessions.pop(str(key),None)

    def request(self,text,conversation_id):
        value=clean(text).casefold()
        value=re.sub(r'^(?:please |jarvis[, ]+)+','',value)
        value=value.replace("what's",'what is')
        hint=speaker_context(self.profile._data)
        key=str(conversation_id) if conversation_id else None
        now=self.now().astimezone(ZONE)
        self.sessions=OrderedDict((k,v) for k,v in self.sessions.items()
            if v['expires']>self.clock() and v['date']==now.date().isoformat()
            and v['revision']==self.profile._data['revision'])
        previous=self.sessions.pop(key,None) if key else None
        same=previous and previous['speaker']==hint['member_id']
        more=value in ('tell me more','more details','show more')
        follow=re.fullmatch(r'(?:and|what about|how about) (?:today|tomorrow|next week|this week|the following week|this weekend|next weekend)',value)
        if same and (more or follow):
            base=previous['brief']
            if more:return Brief(base.subject,base.start,base.end,base.upcoming,True)
            plan=Plan((base.subject,), 'overview',base.start,base.end)
            start,end=resolve_dates(value,now.date().isoformat(),plan)
            return Brief(base.subject,start,end,base.upcoming)
        names=[p for p in self.profile._data.get('members',[]) if re.search(r'\b'+re.escape(p['preferred_name'].casefold())+r'\b',value)]
        # Bounded intent language: do not steal device, travel-search or existing
        # school-finish questions from their accepted handlers.
        day_question=bool(re.fullmatch(r'(?:what does|what will) .+ (?:day|week) look like(?: .+)?',value))
        briefing=bool(re.fullmatch(r'(?:(?:give|show|tell) (?:me|us) |i would like |i want )?(?:(?:a|my|our|the|household|family|daily|morning|personal|benny|linda|mia|emrik)[\s\w\']* )?briefing(?: .+)?',value))
        name_words='|'.join(re.escape(p['preferred_name'].casefold()) for p in self.profile._data.get('members',[]))
        subject_words=r'(?:i|we|'+name_words+r')'
        remainder=DATE_PATTERN.sub('',value).strip()
        next_question=bool(re.fullmatch(
            r'(?:what is next(?: for (?:me|us|the household|'+name_words+r'))?|'
            r'what do '+subject_words+r' have (?:next|left)|'
            r'what is (?:left|remaining) (?:on|in) (?:my|our) (?:day|schedule)|'
            r'what should '+subject_words+r' (?:prepare for|know about))',remainder))
        personal_plans=bool(re.fullmatch(r'(?:what (?:do|does) '+subject_words+r' have (?:on|planned|scheduled)|'
            r'what have (?:i|we) got on|what is on (?:my|our) (?:calendar|schedule))(?: .+)?',value))
        if not (day_question or briefing or next_question or personal_plans):return None
        if not briefing and 'after school' in value:return None
        if re.search(r'\b(weather|news|internet|whatsapp|lights?|blind|camera|door|thermostat|temperature|stocks?|gpu)\b',value):return None
        if not briefing and re.search(r'\b(flights?|travel|trips?|itinerary|layover|stopover)\b',value):return None
        if re.search(r'\b(turn|switch|set|delete|forget|remember|send|cancel|book|unlock|buy|pay)\b',value):return None
        if len(names)>1:raise ValueError('Please ask for one person or the whole household briefing.')
        collective=bool(re.search(r'\b(our|us|we|household|family)\b',value))
        personal=bool(re.search(r'\b(my|me|i)\b',value))
        if day_question and not (names or collective or personal):
            raise ValueError('Whose day would you like to check? Please name a household member.')
        if names:subject=names[0]['id']
        elif collective:subject='all'
        elif personal:
            if not hint['member_id']:raise ValueError('Whose briefing would you like? Please name a household member, or ask again when your voice is matched.')
            subject=hint['member_id']
        elif next_question and same:subject=previous['brief'].subject
        else:subject='all'
        # "my week" has an explicit week view even without a trailing date.
        dates=value
        if not re.search(r'\b(today|tomorrow|weekend|following week|next week|this week|\d{4}-\d{2}-\d{2})\b',value) and re.search(r'\bweek\b',value):
            dates+=' this week'
        start,end=resolve_dates(dates,now.date().isoformat())
        return Brief(subject,start,end,next_question)

    async def handle(self,text,key,*,resolved=None,structured_only=False,targets=None,window='all_day',event_context=False):
        if not shared_knowledge_enabled(getattr(self.profile,'_data',{})):return None
        if len(text)>1000:
            self.clear(key);return None
        try:
            if resolved is not None:
                if not isinstance(resolved,Brief) or resolved.subject not in {'all',*(p['id'] for p in self.profile._data['members'])}:
                    raise ValueError('Invalid briefing subject.')
                validate_range(resolved.start,resolved.end,self.now().astimezone(ZONE).date().isoformat())
                brief=resolved
            else:brief=self.request(text,key)
            if targets is not None and (not targets or not set(targets).issubset({p['id'] for p in self.profile._data['members']})):
                raise ValueError('Invalid briefing targets.')
            if window not in ('all_day','morning','afternoon','evening'):raise ValueError('Invalid planning window.')
        except ValueError as error:return result(str(error),'clarification_required')
        if brief is None:return None
        hint=speaker_context(self.profile._data)
        now=self.now().astimezone(ZONE)
        reference=now.date().isoformat()
        pending={'brief':brief,'speaker':hint['member_id'],'expires':self.clock()+300,
                 'date':reference,'revision':self.profile._data['revision']}
        if key:
            self.sessions[str(key)]=pending
            while len(self.sessions)>100:self.sessions.popitem(last=False)
        start,end=(datetime.fromisoformat(x).replace(tzinfo=ZONE) for x in (brief.start,brief.end))
        selected=set(targets) if targets is not None else ({p['id'] for p in self.profile._data['members']} if brief.subject=='all' else {brief.subject})
        planner=getattr(self.profile,'_planner',None)
        shared_calendar_active=bool(planner is not None and planner.ready)
        source_names=['family'] if 'mia' in selected or shared_calendar_active else []
        if 'benny' in selected:source_names+=['work','travel']
        assignment_gaps=[]
        async def calendar(name):
            entity=SOURCES[name]
            if entity not in self.allowed:return name,None,'not connected or not shared'
            try:
                if name=='family' and shared_calendar_active:
                    raw=await asyncio.wait_for(self.client.get_calendar_events(entity,start,end),10)
                    await planner.enrich(raw,maximum=1)
                else:
                    response=await asyncio.wait_for(self.client.call_service_response('calendar','get_events',{
                        'entity_id':entity,'start_date_time':start.isoformat(),'end_date_time':end.isoformat()}),10)
                    raw=response[entity]['events']
                if not isinstance(raw,list) or len(raw)>500:raise ValueError('Invalid calendar')
                events=[]
                for e in raw:
                    if e.get('status')=='cancelled':continue
                    if name=='family':
                        from jarvis.calendar_membership import assignment
                        meta=planner.assign(e) if planner else assignment(e,{p['id'] for p in self.profile._data['members']})
                        if not meta['members']:
                            assignment_gaps.append('some family calendar appointments have no assigned member');continue
                        if not selected.intersection(meta['members']):continue
                        e={**e,'description':meta['notes'],'location':e.get('location') or meta.get('extracted_location','')}
                        owners=meta['members']
                    else:owners=['benny']
                    item={**interval(e,event_context=event_context),'owners':owners}
                    from jarvis.household_activities import calendar_meaning
                    meaning=calendar_meaning(self.profile._data,item['title'],owners,name,e.get('description',''))
                    if meaning:item['confirmed_activity']=meaning
                    events.append(item)
                return name,[e for e in events if e['end']>start and e['start']<end],None
            except Exception:return name,None,'temporarily unavailable'
        async def summary():
            try:
                data=await asyncio.wait_for(self.client.get_household_today('custom',start_date=brief.start,end_date=brief.end),12)
                validate_range(brief.start,brief.end,reference)
                plan=data['planning']
                if data.get('read_only') is not True or plan['timezone']!='Europe/Oslo' or plan['generated_on']!=reference:
                    raise ValueError('Stale summary')
                dates=[(start+timedelta(days=i)).date().isoformat() for i in range((end-start).days)]
                if [d['date'] for d in plan['days']]!=dates or any(d['timezone']!='Europe/Oslo' for d in plan['days']):
                    raise ValueError('Wrong period')
                for day in plan['days']:
                    if not isinstance(day.get('cards'),list) or len(day['cards'])>100:
                        raise ValueError('Invalid routine summary')
                    for card in day['cards']:
                        if (not isinstance(card,dict) or not isinstance(card.get('title'),str)
                                or not isinstance(card.get('lines'),list) or len(card['lines'])>30
                                or any(not isinstance(line,str) or len(line)>2000 for line in card['lines'])):
                            raise ValueError('Invalid routine card')
                return data
            except Exception:return None
        loaded=await asyncio.gather(summary(),*(calendar(n) for n in source_names))
        if self.now().astimezone(ZONE).date().isoformat()!=reference or self.profile._data['revision']!=pending['revision']:
            if key and self.sessions.get(str(key)) is pending:self.clear(key)
            return result('The household date or saved information changed while I was checking. Please ask again for a fresh briefing.','unavailable')
        if key and self.sessions.get(str(key)) is not pending:
            return result('That briefing was superseded by a newer question. Please ask again.','unavailable')
        snapshot=loaded[0]
        events=[];unavailable=[];sources=[]
        unavailable.extend(dict.fromkeys(assignment_gaps))
        for name,items,error in loaded[1:]:
            if error:unavailable.append(name+' calendar '+error)
            else:
                sources.append(name)
                for item in items:
                    if brief.upcoming and item['end']<=now:continue
                    events.append({**item,'source':name})
        events.sort(key=lambda e:(e['start'],e['source'],e['title']))
        unique=[];seen=set()
        for event in events:
            owners=tuple(event.get('owners',['mia'] if event['source']=='family' else ['benny']))
            identity=(owners,event['start'],event['end'],event['title'])
            if event_context:identity+=(event.get('location'),event.get('description'))
            if identity not in seen:unique.append(event);seen.add(identity)
        if structured_only:
            from jarvis.calendar_evidence import calendar_evidence
            return {**result('Fresh planning evidence checked.'),'provider':'household_briefing','read_only':True,
                'evidence':calendar_evidence(self.profile,brief,unique,snapshot,sources,unavailable,now,targets=targets,window=window,event_context=event_context,shared_calendar_active=shared_calendar_active)}
        person=next((p for p in self.profile._data['members'] if p['id']==brief.subject),None)
        own=person is not None and person['id']==hint['member_id']
        who='your' if own else (person['preferred_name']+"'s" if person else 'the household')
        title='Here is '+who+(' next-up briefing' if brief.upcoming else ' briefing')
        # Portable day formatting (Windows does not support %-d).
        when=start.strftime('%A ')+str(start.day)+start.strftime(' %B')
        if (end-start).days>1:when+=' to '+(end-timedelta(days=1)).strftime('%A %d %B')
        lines=[title+' for '+when+', in Norway time.']
        style=response_style(self.profile._data,hint['member_id'])
        limit=20 if brief.more else (3 if brief.upcoming or style=='concise' else (10 if style=='detailed' else 6))
        for event in unique[:limit]:
            day=event['start'].strftime('%a %d %b')
            if event['all_day']:
                last=(event['end']-timedelta(days=1)).strftime('%a %d %b')
                stamp='all day on '+day if last==day else 'all day from '+day+' through '+last
            elif event['start']<=now<event['end']:stamp='currently scheduled, until '+event['end'].strftime('%a %d %b at %H:%M')
            else:stamp=day+' at '+event['start'].strftime('%H:%M')
            names={p['id']:p['preferred_name'] for p in self.profile._data['members']}
            owner=(' and '.join(names[o] for o in event['owners'])+'’s shared calendar') if event['source']=='family' else 'Benny’s '+event['source']+' calendar'
            lines.append('In '+owner+', “'+event_title(event)+'” is '+stamp+'.')
        if not unique and sources:
            lines.append('I found no '+('remaining ' if brief.upcoming else '')+'entries in the connected '+', '.join(sources)+' calendars for that period; other plans may exist.')
        if len(unique)>limit:lines.append('There are more appointments; say “tell me more” for up to twenty, or ask about a shorter date range.')
        # An overlap is a calendar concern, not evidence of availability or an
        # assignment of Mia's activity to a parent. Ignore untimed/all-day stays.
        overlaps=[]
        timed=[e for e in unique if not e['all_day']]
        for index,a in enumerate(timed):
            for b in timed[index+1:]:
                if b['start']>=a['end']:break
                same_owner=bool(set(a['owners']).intersection(b['owners']))
                if same_owner and a['title']!=b['title']:
                    overlaps.append('“'+event_title(a)+'” and “'+event_title(b)+'”')
        if overlaps:
            lines.append('Calendar entries overlap: '+ '; '.join(overlaps[:2])+'. Please check whether both apply; I have not changed either appointment.')
        if snapshot is not None:
            # Reuse the accepted natural routine formatter, excluding calendar
            # cards already presented chronologically above.
            from copy import deepcopy
            projected=deepcopy(snapshot)
            for day in projected['planning']['days']:
                day['cards']=[c for c in day['cards'] if 'familiekalender' not in c['title']
                    and not c['title'].endswith(' · reported stay')]
                if brief.upcoming and day['date']==reference:
                    for card in day['cards']:
                        if card['title']=='Usual household routine':
                            card['lines']=[line for line in card['lines'] if not re.search(r'\d{2}:\d{2}',line)
                                or max(re.findall(r'\d{2}:\d{2}',line))>=now.strftime('%H:%M')]
                    day['cards']=[c for c in day['cards'] if c['lines']]
                    day['cards']=[c for c in day['cards'] if not re.search(r'\d{2}:\d{2}', ' '.join(c['lines']))
                        or max(re.findall(r'\d{2}:\d{2}', ' '.join(c['lines'])))>=now.strftime('%H:%M')]
            routine=render(projected,Plan((brief.subject,),'overview',brief.start,brief.end),more=brief.more,omit_missing=True)
            if routine:lines.append(routine)
        else:lines.append('The household routine summary could not be read; I have not filled it in from an old answer.')
        if person and person['id'] not in ('mia','benny'):
            lines.append('I do not have a connected personal calendar for '+person['preferred_name']+'; this briefing uses recorded routines only.')
        if unavailable:lines.append('I could not reliably read: '+'; '.join(unavailable)+'. Those appointments are unknown, not empty.')
        if self.reminders is not None:
            try:
                reminders=self.reminders.upcoming(brief.subject,start,end)
                reminders=sorted((r for r in reminders if not (brief.upcoming and r['state']=='delivered'
                    and datetime.fromisoformat(r['due'])<=now)),key=lambda r:r['due'])
                if reminders:
                    lines.append('Saved reminders: '+'; '.join(self.reminders.describe(r) for r in reminders[:limit])+'.')
                    if len(reminders)>limit:lines.append('More reminders exist; ask to show reminders.')
            except Exception:lines.append('Saved reminders could not be read; they are unknown, not empty.')
        return {**result(' '.join(lines)),'provider':'household_briefing','read_only':True,
                'period':{'start':brief.start,'end':brief.end},'sources_checked':sources}
