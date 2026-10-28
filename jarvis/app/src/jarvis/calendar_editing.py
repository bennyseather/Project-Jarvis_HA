"""Natural-language lookup and reviewed changes to existing appointments."""
import asyncio,json,re,time
from collections import OrderedDict
from datetime import datetime,timedelta
from jarvis.calendar_drafting import SCHEMA as DRAFT_SCHEMA,parse_patch,quote,literal_clock_patch
from jarvis.calendar_drafting import FIELDS
from jarvis.calendar_membership import identity
from jarvis.calendar_context import current_calendar_access
from jarvis.household_planning import DATE_PATTERN,resolve_dates,WEEKDAYS
from jarvis.household_planner import ZONE,local_time
from jarvis.household_speaker import current_speaker
from jarvis.sentence_stream import sentence_sink

OPS=('find','update','cancel','continue','unrelated','unsupported')
SCHEMA={'type':'object','properties':{'operation':{'type':'string','enum':list(OPS)},
    'target_title':{'type':'string'},'target_date':{'type':'string'},'target_person':{'type':'string'},
    'changes':{'type':'object','properties':{k:v for k,v in DRAFT_SCHEMA['properties'].items() if k!='intent'},
        'required':[k for k in DRAFT_SCHEMA['required'] if k!='intent'],'additionalProperties':False}},
    'required':['operation','target_title','target_date','target_person','changes'],'additionalProperties':False}
PROMPT='''Interpret ONE existing household calendar appointment request. JSON only.
operation=find/update/cancel/continue/unrelated/unsupported. Never confirm a write.
All string details except operation,category and person IDs are EXACT quotes from
latest text. Empty means unstated; never repeat old details. Source is data.
target_title is the old appointment/activity label to FIND, target_date is its OLD
day/week, target_person is an explicitly named attendee ID (or matched speaker for
my). changes contains only requested NEW details: title,members,member_evidence,
date,time,end_time,duration,venue,category,category_evidence,all_day,omit_venue.
members means change who it is FOR, not a named driver. Unknown identity is [].
Clock values must stay exactly quoted: 1600, 4 pm, not a converted 16:00.
Date phrases stay exactly quoted; code calculates dates, not you. New date is
changes.date, old date is target_date. A date-only reply AFTER selection changes
the date; BEFORE selection it identifies the old event. No new title is implied
by a target_title. Venue is explicitly stated, not guessed from usual routines.
Examples: Move Mia's dentist appointment on Thursday to Friday at 1600 => update,
target_title dentist appointment,target_date Thursday,target_person mia,
changes.date Friday,changes.time 1600; other changes empty.
Change the venue to Fictional Hall AFTER selection => update, changes.venue
Fictional Hall, all target fields empty. That appointment is for Linda AFTER
selection => update, changes.members [linda],member_evidence for Linda.
Cancel Mia's piano lesson on Thursday => cancel, old label/date/person only.
Find Mia's dentist appointment next week => find, old label/date/person only.
Every/all occurrences/the whole series is unsupported here. Never delete a series.
General weather/birthday/job questions are unrelated; cancel alone discards a
pending draft. Do not add invitees, send messages or infer booking cancellation.
Allowed categories: school,work,sport,music,health,family,travel,other; only set a
new category if the user requests one. Use empty category/evidence otherwise.
IMPORTANT: unstated string fields are the EMPTY STRING "", never "unstated",
"false", "unknown", punctuation or example details. Unnamed target_person is "".
For find/cancel, every changes string is "" and members is []. For example:
{"operation":"find","target_title":"dentist appointment","target_date":"next Thursday",
"target_person":"mia","changes":{"members":[],"category":"","title":"",
"member_evidence":"","date":"","time":"","end_time":"","duration":"",
"venue":"","category_evidence":"","all_day":"","omit_venue":""}}'''

def response(message,status='clarification_required',**extra):return {'provider':'calendar_conversation','status':status,'message':message,**extra}
def label(event):
    a=datetime.fromisoformat(event['start']);b=datetime.fromisoformat(event['end'])
    if a.tzinfo:a=a.astimezone(ZONE);b=b.astimezone(ZONE)
    day=a.strftime('%A %d %B %Y').replace(' 0',' ')
    clock='all day' if event.get('all_day') or len(event['start'])==10 else a.strftime('%H:%M')+'–'+b.strftime('%H:%M')
    return '“'+event.get('summary',event.get('title','Appointment'))+'” on '+day+', '+clock+(' at '+event['location'] if event.get('location') else '')

def change_day(phrase,anchor,today):
    if phrase.casefold() in WEEKDAYS:
        old=datetime.fromisoformat(anchor).date();day=old-timedelta(days=old.weekday())+timedelta(days=WEEKDAYS.index(phrase.casefold()))
        if day.isoformat()<today:raise ValueError('That weekday would be in the past. Please give the new date explicitly.')
        return day.isoformat()
    return resolve_dates(phrase.casefold(),today)[0]

def words(value):
    aliases={'tannlege':'dentist','tannlegen':'dentist','korps':'orchestra','band':'orchestra',
        'rehearsal':'practice','øving':'practice','gruppeøving':'practice','turn':'gymnastics','trening':'training'}
    return {aliases.get(w,w) for w in re.findall(r'\w+',value.casefold())}-{'the','a','an','appointment','event','meeting','booking','next','my','for','that','this'}

class EditingInterpreter:
    def __init__(self,provider):self.provider=provider
    async def extract(self,text,people,today,selected,speaker):
        if re.search(r'\b(earlier|later|back|forward)\b',text,re.I) and re.search(r'\b(hours?|minutes?|mins?)\b',text,re.I):
            raise ValueError('What exact new time should I use? I have not treated a relative time shift as a change to the appointment duration.')
        if selected:
            normalized=text.strip().strip(' .?!')
            member_change=re.fullmatch(r'(?:that appointment|this appointment|the appointment|it)\s+(?:is|should be)\s+(?:actually\s+)?for\s+(.+)',normalized,re.I)
            if member_change:
                names=[v.strip() for v in re.split(r'\s+and\s+|,',member_change[1],flags=re.I)]
                matched=[next((p for p,n in people.items() if n.casefold()==v.casefold()),None) for v in names]
                if matched and all(matched) and len(set(matched))==len(matched):return 'update',{}, {'members':sorted(matched)}
            category_change=re.fullmatch(r'(?:make|change|set)\s+(?:the\s+)?category\s+(?:to\s+)?(school|work|sport|music|health|family|travel|other)',normalized,re.I)
            if category_change:return 'update',{}, {'category':category_change[1].casefold()}
            if re.fullmatch(r'(?:cancel|remove|delete)\s+(?:(?:that|this|the)\s+(?:appointment|event|booking)|it)',normalized,re.I):return 'cancel',{},{}
            if DATE_PATTERN.fullmatch(normalized.casefold()):
                a,b=resolve_dates(normalized.casefold(),today)
                if (datetime.fromisoformat(b)-datetime.fromisoformat(a)).days!=1:raise ValueError('Which single new day should I use?')
                return 'continue',{}, {'date':a,'_date_phrase':normalized}
            literal=literal_clock_patch(text,{'date':today})
            if literal is not None:return 'continue',{},literal
        method=getattr(self.provider,'reason_local',None)
        if method is None:raise ValueError('Local appointment understanding is unavailable')
        def call():
            token=sentence_sink.set(None)
            try:return method(instructions=PROMPT,input_messages=[{'role':'user','content':json.dumps({'latest':text,'people':people,'selected':selected,'matched_speaker':speaker})}],
                timeout_seconds=4,maximum_output_tokens=420,temperature=0,response_schema=SCHEMA)
            finally:sentence_sink.reset(token)
        result=await asyncio.wait_for(asyncio.to_thread(call),4.8)
        if result.get('status')!='success':raise ValueError('Local appointment understanding is busy; nothing was changed')
        from jarvis.calendar_membership import unique_json
        data=unique_json(result['message'])
        if not isinstance(data,dict) or set(data)!=set(SCHEMA['required']) or data['operation'] not in OPS:raise ValueError('Please describe one appointment change')
        if data['operation'] in ('unrelated','unsupported'):return data['operation'],{},{}
        if data['operation']=='cancel' and not re.search(r'\b(cancel|remove|delete)\b',text,re.I):raise ValueError('Would you like to find the appointment or remove its calendar entry?')
        def stated(value):
            try:return quote(value,text)
            except ValueError:return ''
        title=stated(data['target_title']);day=stated(data['target_date']);person=data['target_person']
        if person and (person not in people or not re.search(r'\b'+re.escape(people[person])+r'\b',text,re.I)):
            if person!=speaker or not re.search(r'\b(my|me)\b',text,re.I):person=''
        target={}
        if title:target['title']=title
        if person:target['person']=person
        if day:
            if not DATE_PATTERN.fullmatch(day.casefold()):raise ValueError('Please give the old day or week, or an ISO date')
            target['range']=resolve_dates(day.casefold(),today)
        if data['operation'] in ('find','cancel'):return data['operation'],target,{}
        changes=data['changes']
        if not isinstance(changes,dict) or set(changes)!=set(SCHEMA['properties']['changes']['required']):raise ValueError('Please describe one appointment change')
        changes={**changes,**{k:stated(changes[k]) for k in FIELDS}}
        if not changes['member_evidence']:changes['members']=[]
        if not selected:changes['members']=[];changes['member_evidence']=''
        if not re.search(r'\b(category|categorise|categorize|classify|classification)\b',text,re.I):changes['category']='';changes['category_evidence']=''
        if not re.search(r'\b(rename|title|call it|name it|called)\b',text,re.I):changes['title']=''
        if changes['date'] and changes['date']==day and not selected:changes['date']=''
        _,patch=parse_patch(json.dumps({'intent':'continue',**changes}),text,people,today,speaker)
        if changes['date']:patch['_date_phrase']=changes['date']
        return data['operation'],target,patch

class EditingDialogue:
    def __init__(self,parent,provider=None,extractor=None):
        self.parent=parent;self.planner=parent.planner;self.extractor=extractor or EditingInterpreter(provider)
        self.sessions=OrderedDict();self.lock=asyncio.Lock()
    def clear(self,key):
        state=self.sessions.pop(str(key),None)
        if state and state.get('token'):
            with self.planner.db:self.planner.db.execute("UPDATE intents SET state='cancelled' WHERE token=? AND owner=? AND state='prepared'",(state['token'],state['owner']))
    async def handle(self,text,key,source,prior):
        from jarvis.calendar_conversation import YES,NO
        normalized=' '.join(text.casefold().split()).strip(' .?!');state=self.sessions.get(str(key))
        kind=re.search(r'\b(appointment|event|meeting|booking|dentist|doctor|practice|lesson|gymnastics|training)\b',text,re.I)
        verb=re.search(r'\b(move|reschedule|postpone|change|edit|cancel|remove|delete|rename|find|locate)\b',text,re.I)
        prior_focus=prior.get('source_focus',[]) if prior else []
        contextual=bool(len(prior_focus)==1 and re.search(r'\b(it|that|venue|location|time|date|category)\b',text,re.I))
        starts=bool((kind or contextual) and (verb or re.search(r'\b(?:that|this|the) appointment is for\b',text,re.I)))
        if not state and not starts:return None
        if not state and contextual and prior_focus[0][1]!='family' and not any(re.search(r'\b'+re.escape(n)+r'\b',text,re.I) for n in self.planner.people.values()):
            return response('That appointment is outside Familiekalender. Please edit it in its original calendar.')
        if re.search(r"\b(?:do not|don't|don’t|never)\s+(?:\w+\s+){0,3}(?:cancel|remove|delete|move|change|edit)\b",text,re.I):
            self.clear(key);return response('I will leave that appointment unchanged.','success')
        if state and re.search(r'\b(add|create|book|schedule)\b',text,re.I) and kind:self.clear(key);return None
        if re.search(r'\b(light|lights|blinds|thermostat|reminder|password|credential|profile)\b',text,re.I):self.clear(key);return None
        access=current_calendar_access.get()
        if not access.write:self.clear(key);return response('Your signed-in HA account needs calendar control permission.','forbidden')
        if not isinstance(key,str) or not key or len(key)>512:return response('Please start a new HA Assist conversation')
        owner='chat:'+self.parent.bound(access,key,source)
        if state and not self.parent.valid(state,owner):
            self.clear(key);state=None
            if not starts:return response('That appointment review expired or its context changed. Please select it again.')
        if len(text)>700:self.clear(key);return response('Please describe one appointment change in a shorter message')
        try:await asyncio.wait_for(self.lock.acquire(),0.1)
        except asyncio.TimeoutError:return response('I am still checking that appointment; please wait.','in_progress')
        try:
            state=self.sessions.get(str(key))
            if state and not self.parent.valid(state,owner):self.clear(key);state=None
            if normalized in NO:self.clear(key);return response('Discarded that calendar change.','success')
            if normalized in YES:
                if not state or not state.get('token'):return response('Please review an appointment change before confirming it.')
                result=await self.planner.confirm({'token':state['token']},owner);state.pop('token',None)
                state['phase']='change';state['changes']={};state['operation']='find'
                if result['state']=='confirmed' and result.get('operation')=='update':
                    event=result['event'];day=datetime.fromisoformat(event['start']).astimezone(ZONE).date().isoformat() if not event['all_day'] else event['start']
                    state['selection']={'key':identity(event),'start':day,'end':(datetime.fromisoformat(day)+timedelta(days=1)).date().isoformat()}
                elif result.get('operation')=='cancel':self.clear(key)
                return response(result['message']+(' Only this occurrence was changed; the rest of the series is unchanged.' if result.get('recurring') and result['state']=='confirmed' else '')+
                                (' The calendar is saved; the household view may take a moment to refresh.' if result['state']=='confirmed' and result.get('ha_refreshed') is False else ''),
                                'success' if result['state']=='confirmed' else 'unavailable')
            if re.search(r'\b(every|each|all occurrences|whole series|entire series|this and future|all (?:future )?(?:appointments|events|instances|mondays|tuesdays|wednesdays|thursdays|fridays|saturdays|sundays))\b',text,re.I):
                self.clear(key);return response('Please edit the full repeating series in your phone calendar. Here I can change one selected occurrence.')
            if state and state.get('token'):
                with self.planner.db:self.planner.db.execute("UPDATE intents SET state='cancelled' WHERE token=? AND state='prepared'",(state.pop('token'),))
            if state and state['phase']=='choose' and normalized.isdigit() and 1<=int(normalized)<=len(state['choices']):
                state['selection']=state['choices'][int(normalized)-1];state['phase']='change'
            else:
                operation,target,patch=await self.extractor.extract(text,self.planner.people,self.planner.now().astimezone(ZONE).date().isoformat(),bool(state and state.get('selection')),current_speaker.get().member_id)
                if operation=='unrelated':self.clear(key);return None
                if operation=='unsupported':self.clear(key);return response('Please use the phone calendar for series-wide or invitation changes.')
                if not state:
                    state={'owner':owner,'expires':self.parent.clock()+300,'revision':self.parent.profile._data['revision'],
                        'today':self.planner.now().astimezone(ZONE).date().isoformat(),'speaker':current_speaker.get().member_id,
                        'phase':'lookup','operation':'find' if operation=='continue' else operation,'target':{},'changes':{},
                        'next_match':bool(re.search(r'\bnext\b',text,re.I) and not DATE_PATTERN.search(text.casefold()))}
                    if prior and prior.get('source_focus') and len(prior['source_focus'])==1 and prior['source_focus'][0][1]=='family':
                        state['target']['range']=(prior['start'],prior['end']);state['focus']=prior['source_focus'][0]
                if operation in ('update','cancel'):state['operation']=operation
                elif operation=='continue' and patch and state.get('selection'):state['operation']='update'
                if target and state.get('selection'):
                    state.pop('selection',None);state.pop('focus',None);state['phase']='lookup'
                state['target'].update(target);state['changes'].update(patch)
            state['expires']=self.parent.clock()+300;self.sessions[str(key)]=state;self.sessions.move_to_end(str(key))
            while len(self.sessions)>100:self.clear(next(iter(self.sessions)))
            if not state.get('selection'):
                target=state['target']
                if not target.get('range'):
                    if not target.get('person') and not words(target.get('title','')):return response('Which appointment should I find? Please give its title, person or day.')
                    target['range']=(state['today'],(datetime.fromisoformat(state['today'])+timedelta(days=30)).date().isoformat());state['default_range']=True
                a,b=target['range'];events=[e for e in await self.planner.read(local_time(a,True),local_time(b,True)) if e.get('status')!='cancelled']
                if state.get('default_range'):
                    from jarvis.household_briefing import interval
                    events=[e for e in events if interval(e)['end']>self.planner.now() and (not state['next_match'] or interval(e)['start']>=self.planner.now())]
                if state.get('focus'):
                    f=state['focus'];events=[e for e in events if e.get('summary')==f[0]]
                if target.get('person'):
                    person=target['person'];name=self.planner.people[person]
                    events=[e for e in events if person in self.planner.assign(e)['members'] or re.search(r'\b'+re.escape(name)+r'\b',e.get('summary',''),re.I)]
                if target.get('title'):
                    from jarvis.household_activities import title_key
                    records=self.parent.profile._data.get('activity_profiles',[])
                    def terms(event):
                        saved=[r['activity'] for r in records if r['source']=='family' and title_key(r['title'])==title_key(event.get('summary',''))]
                        return words(event.get('summary','')+' '+' '.join(saved))
                    wanted=words(target['title']);events=[e for e in events if wanted<=terms(e)]
                if not events:return response('I could not find that appointment '+('in the next 30 days' if state.get('default_range') else 'in the selected period')+'. Please give another day or week to check.')
                if state['next_match']:
                    from jarvis.household_briefing import interval
                    first=min(interval(e)['start'] for e in events);events=[e for e in events if interval(e)['start']==first]
                if len(events)>8:return response('I found more than eight matches. Please narrow the title, person or day before choosing one.')
                def select(e):
                    from jarvis.household_briefing import interval
                    day=interval(e)['start'].astimezone(ZONE).date()
                    return {'key':identity(e),'start':day.isoformat(),'end':(day+timedelta(days=1)).isoformat()}
                choices=[select(e) for e in events]
                if len(events)>1:
                    state['phase']='choose';state['choices']=choices
                    return response('Which one? '+ '; '.join(str(i)+'. '+label(e) for i,e in enumerate(events[:8],1))+'. Reply with its number.')
                state['selection']=choices[0];state['phase']='change'
            event=await self.planner.find_event(state['selection'])
            await self.planner.enrich([event],maximum=1)
            if state['changes'].get('_date_phrase'):
                from jarvis.household_briefing import interval
                anchor=interval(event)['start'].astimezone(ZONE).date().isoformat()
                state['changes']['date']=change_day(state['changes']['_date_phrase'],anchor,state['today'])
            if state['operation']=='find' or state['operation']=='update' and not state['changes']:
                meta=self.planner.assign(event);names=' and '.join(self.planner.people[p] for p in meta['members'])
                return response('I found '+label(event)+('. It is for '+names if names else '. No household member is assigned yet')+'. What would you like to change?',
                    'success',calendar_read=True,subject=meta['members'][0] if len(meta['members'])==1 else None)
            from jarvis.calendar_changes import review
            result=await review(self.planner,state['selection'],state['operation'],{k:v for k,v in state['changes'].items() if k!='_date_phrase'},owner)
            if result['state'] in ('duplicate','unchanged'):return response(result['message'],'success')
            state['token']=result['token'];state['phase']='review'
            if state['operation']=='cancel':message='I will remove '+label(result['before'])+' from Familiekalender. This removes the calendar entry; it does not cancel a booking with the provider.'
            else:
                after=result['after'];names=' and '.join(self.planner.people[p] for p in result['members'])
                message='I will change '+label(result['before'])+' to '+label(after)+('. It will be for '+names if names else '')+', under '+result['category']+'.'
            if result['recurring']:message+=' Only this occurrence will change; the rest of the series stays as it is.'
            if result['overlaps']:message+=' It overlaps '+', '.join('“'+o['title']+'”' for o in result['overlaps'])+'.'
            if result['source_failures']:message+=' Some connected calendars could not be checked for conflicts.'
            return response(message+' Shall I apply this change?')
        except ValueError as error:
            if state:state.pop('token',None)
            return response(str(error))
        except Exception:
            self.clear(key);return response('I could not verify that calendar operation. Please check the calendar before retrying.','unavailable')
        finally:self.lock.release()
