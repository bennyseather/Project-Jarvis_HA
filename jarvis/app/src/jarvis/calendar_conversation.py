"""Session-bound calendar drafting over the existing durable planner journal."""
import asyncio
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
import hashlib
import re
import time
from jarvis.calendar_context import current_calendar_access
from jarvis.calendar_drafting import CalendarDrafting
from jarvis.calendar_membership import identity
from jarvis.household_planner import ZONE, local_time
from jarvis.household_speaker import current_speaker

YES={'yes','yes please','confirm','confirmed','save it','save','add it','go ahead','proceed','approve','approved'}
NO={'no','no thanks','cancel','never mind','nevermind','stop','discard'}
CREATE=re.compile(r'\b(add|create|schedule|book|put)\b',re.I)
CALENDAR=re.compile(r'\b(appointments?|calendar|meetings?|dentist|doctor|practice|training|lessons?|birthday party)\b',re.I)
CORRECT=re.compile(r'\b(?:that|this|the) (?:appointment|event|meeting|booking)\b.{0,100}\b(?:for|belongs|category|classif|venue|location)\b',re.I)
EXCLUDE=re.compile(r'\b(remind|reminder|automation|light|lights|thermostat|password|api.key|credential)\b',re.I)
UNSUPPORTED=re.compile(r'\b(every|recurring|repeat|weekly|monthly|delete|remove|reschedule|move|cancel (?:that|the|my|this))\b',re.I)
INSPECT=re.compile(r'^(?:who is|who.s|whose|which (?:family|household) member|what category|how is)\b',re.I)

def reply(message,status='clarification_required'):
    return {'provider':'calendar_conversation','status':status,'message':message}

class CalendarConversation:
    def __init__(self,planner,provider=None,*,clock=time.monotonic,extractor=None):
        self.planner=planner;self.profile=planner.profile;self.clock=clock
        self.extractor=extractor or CalendarDrafting(provider)
        self.sessions=OrderedDict();self.lock=asyncio.Lock()
        from jarvis.calendar_editing import EditingDialogue
        self.editing=EditingDialogue(self,provider)

    def clear(self,key):
        state=self.sessions.pop(str(key),None)
        if state and state.get('token'):
            with self.planner.db:
                self.planner.db.execute("UPDATE intents SET state='cancelled' WHERE token=? AND owner=? AND state='prepared'",
                                        (state['token'],state['owner']))

    def bound(self,access,key,source):
        return hashlib.sha256(repr((access.actor,str(key),source or '')).encode()).hexdigest()

    def valid(self,state,owner):
        return (state['owner']==owner and state['expires']>self.clock() and
                state['speaker']==current_speaker.get().member_id and
                state['revision']==self.profile._data['revision'] and
                state['today']==self.planner.now().astimezone(ZONE).date().isoformat())

    async def handle(self,text,key,source_id=None,prior=None):
        normalized=' '.join(text.casefold().split()).strip(' .?!')
        if INSPECT.search(text) and (CALENDAR.search(text) or prior and re.search(r'\bit\b',text,re.I)):
            self.clear(key)
            if not current_calendar_access.get().read:return reply('Your HA account needs access to Familiekalender.','forbidden')
            try:return await self.classification(text,prior)
            except Exception:return reply('I could not verify that appointment just now. Please check the Household planner.','unavailable')
        old=self.sessions.get(str(key))
        if hasattr(self.planner.client,'manage_household_appointment') and not (old and old['kind']=='create' and old['phase']!='done'):
            editing=await self.editing.handle(text,key,source_id,prior)
            if editing is not None:self.clear(key);return editing
        starts=bool(not EXCLUDE.search(text) and (CORRECT.search(text) or
                    (CREATE.search(text) and (CALENDAR.search(text) or re.search(r'\b(tomorrow|next|\d{4}-\d{2}-\d{2})\b',text,re.I)))))
        if not old and not starts:return None
        access=current_calendar_access.get()
        if not access.write:
            self.clear(key)
            return reply('Please use an authenticated HA account with permission to manage Familiekalender. Voice recognition does not grant calendar permissions.','forbidden')
        if not isinstance(key,str) or not key or len(key)>512:
            return reply('Please start a new HA Assist conversation before adding an appointment.')
        owner='chat:'+self.bound(access,key,source_id)
        if old and not self.valid(old,owner):
            self.clear(key)
            if not starts:return reply('That calendar draft expired or its context changed. Please describe the appointment again.')
            old=None
        if len(text)>700:
            self.clear(key);return reply('Please describe one appointment in a shorter message.')
        try:await asyncio.wait_for(self.lock.acquire(),0.1)
        except asyncio.TimeoutError:return reply('I am still checking that calendar request. Nothing else has been saved; please wait.','in_progress')
        try:
            # Recheck after acquiring the lock; another confirmation may have completed.
            old=self.sessions.get(str(key))
            if old and not self.valid(old,owner):self.clear(key);old=None
            return await self._handle(text,normalized,key,source_id,owner,old,starts,prior)
        except (ValueError,KeyError,TypeError,asyncio.TimeoutError) as error:
            self.clear(key)
            message=str(error) if isinstance(error,ValueError) else 'I could not finish checking that appointment. Nothing further was sent; please review the calendar before trying again.'
            return reply(message or 'I could not check the calendar just now. Please try again.','unavailable')
        except Exception:
            self.clear(key)
            return reply('I could not verify the calendar operation. Please check Familiekalender before trying again; I will not retry a save automatically.','unavailable')
        finally:self.lock.release()

    async def _handle(self,text,normalized,key,source,owner,state,starts,prior):
        if state and state['kind']=='create' and re.fullmatch(r'(?:cancel|remove|delete) (?:that|this|the) appointment',normalized):
            self.clear(key);return reply('Discarded that unsaved appointment. Nothing was added to the calendar.','success')
        if normalized in NO:
            self.clear(key);return reply('Discarded that calendar draft. No further calendar changes will be made.','success')
        if normalized in YES:
            if not state or state['phase']!='review':return reply('There is no calendar review waiting for confirmation. Please describe the appointment first.')
            # Permissions, expiry, date, revision and actor/source were checked this turn;
            # the planner rechecks live duplicates/overlaps/source hash under its lock.
            result=await self.planner.confirm({'token':state['token']},owner)
            state['phase']='done';state.pop('token',None)
            return reply(result['message'],'success' if result['state'] in ('confirmed','duplicate') else 'unavailable')
        if UNSUPPORTED.search(text) and (starts or state):
            self.clear(key)
            return reply('Please change repeats, dates or remove existing appointments in your phone calendar for now. Here I can add one reviewed appointment or correct its Jarvis member/category assignment.')
        if state and state['phase']=='choose':
            matches=[c for i,c in enumerate(state['choices'],1) if normalized==str(i) or normalized==c['title'].casefold()]
            if len(matches)==1:
                state['selection']=matches[0]['selection'];state['phase']='correct'
                return await self.assignment_review(state)
        if state and state['phase']=='done':state=None
        if state and state.get('token'):
            # Any revision needs a fresh review, never an old yes against new details.
            with self.planner.db:self.planner.db.execute("UPDATE intents SET state='cancelled' WHERE token=? AND state='prepared'",(state.pop('token'),))
            state['phase']='collect' if state['kind']=='create' else 'correct'
        partial=state.get('draft',{}) if state else {}
        speaker=current_speaker.get().member_id
        intent,patch=await self.extractor.extract(text,self.planner.people,
            self.planner.now().astimezone(ZONE).date().isoformat(),partial,speaker)
        if intent=='unrelated':self.clear(key);return None
        if intent=='unsupported':
            self.clear(key);return reply('Please make that change in your phone calendar. I can prepare one new appointment or a reviewed member/category correction here.')
        if not state:
            if intent not in ('create','correct'):return reply('Would you like to add an appointment, or correct an existing one?')
            state={'owner':owner,'expires':self.clock()+300,'revision':self.profile._data['revision'],
                'today':self.planner.now().astimezone(ZONE).date().isoformat(),
                'speaker':current_speaker.get().member_id,
                'kind':'create' if intent=='create' else 'assignment','phase':'collect' if intent=='create' else 'correct','draft':{}}
            if state['kind']=='assignment' and prior and prior.get('start') and prior.get('end'):
                state['range']=(prior['start'],prior['end'])
                focus=prior.get('source_focus',[])
                if len(focus)==1 and focus[0][1]=='family':state['focus']=focus[0]
        elif intent=='create' and starts:
            self.clear(key)
            return await self._handle(text,normalized,key,source,owner,None,starts,prior)
        state['draft'].update(patch);state['expires']=self.clock()+300
        self.sessions[str(key)]=state;self.sessions.move_to_end(str(key))
        while len(self.sessions)>100:self.clear(next(iter(self.sessions)))
        if state['kind']=='assignment':return await self.locate(state)
        return await self.prepare(state)

    async def prepare(self,state):
        d=state['draft'];people=self.planner.people
        for field,question in (
            ('title','What is the appointment called?'),('members','Who is the appointment for?'),
            ('date','Which day is it?'),('time','What time does it start?')):
            if field=='time' and d.get('all_day'):continue
            if not d.get(field):return reply(question)
        if any(re.search(r'(?<!\w)'+re.escape(name)+r'(?!\w)',d['title'],re.I) for p,name in people.items() if p not in d['members']):
            return reply('The title names someone different from the assigned person. What title should I use?')
        if not d.get('all_day') and not d.get('end_time') and not d.get('duration'):
            return reply('How long should I allow, or what time does it finish?')
        if not d.get('venue_known'):return reply('Where is it? If you do not know yet, say “venue unknown”.')
        if d.get('all_day'):start=end=d['date']
        else:
            start=d['date']+'T'+d['time'];a=local_time(start)
            if a<=self.planner.now().astimezone(ZONE):raise ValueError('That start time has already passed. Which future date and time should I use?')
            if d.get('duration'):b=(a.astimezone(timezone.utc)+timedelta(minutes=d['duration'])).astimezone(ZONE);end=b.strftime('%Y-%m-%dT%H:%M')
            else:
                end=d['date']+'T'+d['end_time']
                if local_time(end)<=a:raise ValueError('The end must be after the start on that day. Please give a duration if it ends the following day.')
        payload={'title':d['title'],'members':d['members'],'category':d.get('category','other'),
                 'start':start,'end':end,'all_day':bool(d.get('all_day')),'location':d.get('location',''),'notes':''}
        result=await self.planner.review(payload,state['owner'])
        if result['state']=='duplicate':state['phase']='done';return reply(result['message'],'success')
        state['token']=result['token'];state['phase']='review'
        when=datetime.fromisoformat(start).strftime('%A %d %B %Y').replace(' 0',' ')
        times='all day' if d.get('all_day') else d['time']+'–'+end[-5:]+(' (ends '+end[:10]+')' if end[:10]!=start[:10] else '')
        names=' and '.join(self.planner.people[p] for p in d['members'])
        message=f'I will add “{d["title"]}” for {names} on {when}, {times} Norway time, '+('at '+d['location'] if d.get('location') else 'with no venue recorded')+f', under {d.get("category","other")}.'
        if result['overlaps']:
            message+=' It overlaps '+', '.join('“'+o['title']+'”' for o in result['overlaps'])+'.'
        if result['source_failures']:message+=' I could not check every connected calendar for overlaps.'
        return reply(message+' Shall I save it to Familiekalender?')

    async def locate(self,state):
        d=state['draft']
        if 'selection' in state:return await self.assignment_review(state)
        if d.get('date'):
            a=d['date'];b=(datetime.fromisoformat(a)+timedelta(days=1)).date().isoformat()
        elif state.get('range'):a,b=state['range']
        else:return reply('Which day is the existing appointment on, and what is it called?')
        events=await self.planner.read(local_time(a,True),local_time(b,True))
        events=[e for e in events if e.get('status')!='cancelled']
        if state.get('focus'):
            focus=state['focus']
            # Match the previously selected source identity against fresh source data.
            from jarvis.calendar_membership import stamp
            events=[e for e in events if e.get('summary')==focus[0] and stamp(e['start'])==stamp(focus[2]) and stamp(e['end'])==stamp(focus[3])]
        elif d.get('title'):events=[e for e in events if d['title'].casefold() in e.get('summary','').casefold()]
        if not events:return reply('I could not identify that appointment. Please give its exact title and day, or use Review on the Household page.')
        if len(events)>1:
            state['phase']='choose';state['choices']=[{'title':e.get('summary','Appointment'),'selection':{'key':identity(e),'start':a,'end':b}} for e in events[:8]]
            return reply('Which one? '+ '; '.join(f'{i}. {c["title"]}' for i,c in enumerate(state['choices'],1))+'. Reply with its number.')
        state['selection']={'key':identity(events[0]),'start':a,'end':b}
        return await self.assignment_review(state)

    async def assignment_review(self,state):
        d=state['draft'];event=await self.planner.find_event(state['selection']);current=self.planner.assign(event)
        if any(k in d for k in ('location','time','duration','end_time','all_day')):
            return reply('For an existing appointment, please edit its venue or time on your phone. I can correct who it belongs to and its category in Jarvis. Say cancel to discard this request.')
        if not d.get('members') and not d.get('category'):return reply('Who should this appointment belong to, or which category should it use?')
        members=d.get('members',current['members']);category=d.get('category',current['category'])
        if not members:return reply('Who is this appointment for?')
        result=await self.planner.review_assignment({**state['selection'],'members':members,'category':category},state['owner'])
        state['token']=result['token'];state['phase']='review'
        names=' and '.join(self.planner.people[p] for p in members)
        return reply(f'I will catalogue “{event.get("summary","Appointment")}” under {names}, category {category}. This changes its Jarvis assignment; the phone calendar entry stays as it is. Shall I save that correction?')

    async def classification(self,text,prior):
        """Explain current catalogue metadata without a write-capable model call."""
        from jarvis.household_planning import DATE_PATTERN,resolve_dates
        from jarvis.calendar_membership import stamp
        self.planner.guard();match=DATE_PATTERN.search(text.casefold())
        if match:a,b=resolve_dates(match[0],self.planner.now().astimezone(ZONE).date().isoformat())
        elif prior:a,b=prior['start'],prior['end']
        else:return reply('Which appointment and day should I check? You can also ask just after selecting an appointment in this conversation.')
        events=[e for e in await self.planner.read(local_time(a,True),local_time(b,True)) if e.get('status')!='cancelled']
        exact=[e for e in events if e.get('summary') and e['summary'].casefold() in text.casefold()]
        focus=prior.get('source_focus',[]) if prior and not match else []
        if exact:events=exact
        elif len(focus)==1 and focus[0][1]=='family':
            f=focus[0];events=[e for e in events if e.get('summary')==f[0] and stamp(e['start'])==stamp(f[2]) and stamp(e['end'])==stamp(f[3])]
        if len(events)!=1:return reply('Which appointment do you mean? Please include its title and day.')
        await self.planner.enrich(events,maximum=1)
        meta=self.planner.assign(events[0]);names=' and '.join(self.planner.people[p] for p in meta['members'])
        message=f'“{events[0].get("summary","Appointment")}” '+('is catalogued for '+names if names else 'has no confirmed household member assigned')+f', under {meta["category"]}.'
        message+=' This is based on '+meta['basis']+'.'
        return {**reply(message,'success'),'calendar_read':True}
