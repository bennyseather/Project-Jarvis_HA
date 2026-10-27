"""Shared phone-calendar agenda and explicit reviewed writes. No model actions.

Google calendar is authoritative. SQLite holds only assignment annotations and
write receipts, not a second calendar. Uncertain writes are never retried blindly.
"""
import asyncio
from datetime import date,datetime,timedelta,timezone
import hashlib
import json
from pathlib import Path
import secrets
import sqlite3
import time
from zoneinfo import ZoneInfo
from jarvis.calendar_membership import CATEGORIES,PREFIX,assignment,description,identity
from jarvis.household_speaker import shared_knowledge_enabled

ZONE=ZoneInfo('Europe/Oslo')
CALENDAR='calendar.familiekalender'

def local_time(value,all_day=False):
    if not isinstance(value,str):raise ValueError('Choose a date and time')
    if all_day:
        if len(value)!=10:raise ValueError('Use a calendar date')
        return datetime.combine(date.fromisoformat(value),datetime.min.time(),ZONE)
    if len(value)!=16:raise ValueError('Use a date and 24-hour time')
    naive=datetime.fromisoformat(value)
    if naive.tzinfo is not None:raise ValueError('Use Norway local time')
    matches={candidate.astimezone(timezone.utc) for fold in (0,1)
        if (candidate:=naive.replace(tzinfo=ZONE,fold=fold)).astimezone(timezone.utc).astimezone(ZONE).replace(tzinfo=None)==naive}
    if len(matches)!=1:raise ValueError('That time is missing or ambiguous during a clock change; choose an unambiguous time')
    return next(iter(matches)).astimezone(ZONE)

def text(value,limit,required=False):
    if not isinstance(value,str) or len(value)>limit or any(ord(c)<32 and c not in '\n\t' for c in value):raise ValueError('Invalid appointment text')
    value=value.strip()
    if required and not value:raise ValueError('Enter an appointment title')
    return value

class HouseholdPlanner:
    def __init__(self,profile,client,allowed,*,path=None,now=None,clock=time.time):
        self.profile,self.client,self.allowed=profile,client,frozenset(allowed)
        self.now=now or (lambda:datetime.now(ZONE));self.clock=clock;self.lock=asyncio.Lock()
        self.path=Path(path) if path else None
        if self.path:self.path.parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(str(self.path) if self.path else ':memory:')
        if self.path:self.path.chmod(0o600)
        self.db.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY,value TEXT NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS assignments (key TEXT PRIMARY KEY,value TEXT NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS intents (token TEXT PRIMARY KEY,owner TEXT NOT NULL,expires REAL NOT NULL,fingerprint TEXT NOT NULL,payload TEXT NOT NULL,state TEXT NOT NULL)')
        self.db.commit();self._active=self.ready;profile._planner=self
    @property
    def people(self):return {p['id']:p['preferred_name'] for p in self.profile._data['members']}
    @property
    def ready(self):
        self._active=self.db.execute("SELECT value FROM settings WHERE key='bootstrap'").fetchone() is not None
        return self._active
    def annotations(self):return {k:json.loads(v) for k,v in self.db.execute('SELECT key,value FROM assignments')}
    def project(self):
        return {'schema_version':1,'calendar':CALENDAR,'ready':self.ready,'members':[{'id':i,'name':n} for i,n in self.people.items()],
            'categories':list(CATEGORIES),'assignments':self.annotations(),'activities':self.profile.context().get('confirmed_activity_profiles',[])}
    def guard(self,write=False):
        if not shared_knowledge_enabled(self.profile._data):raise ValueError('Shared household knowledge is disabled')
        if CALENDAR not in self.allowed:raise ValueError('Familiekalender is not exposed to Jarvis')
        if write and not self.ready:raise ValueError('The shared planner has not been activated yet')
    def assign(self,event):return assignment(event,self.people,self.annotations(),self.ready)
    def bootstrap(self,events):
        """One deployment-time migration, not a browser operation. No calendar writes."""
        self.guard()
        if self.ready:raise ValueError('Existing assignments must not be re-imported')
        if len(events)>5000:raise ValueError('Unbounded migration')
        with self.db:
            for event in events:
                if event.get('status')=='cancelled':continue
                record=assignment(event,self.people,{},True)
                if str(event.get('description') or '').startswith(PREFIX) and not record['planner_id']:
                    raise ValueError('An existing appointment has invalid planner metadata; review before activation')
                if not record['planner_id']:
                    self.db.execute('INSERT OR IGNORE INTO assignments VALUES (?,?)',(identity(event),json.dumps({'members':['mia'],'category':self.category(event,['mia'])})))
            self.db.execute('INSERT INTO settings VALUES (?,?)',('bootstrap',self.now().isoformat()))
        self._active=True
        return self.db.execute('SELECT count(*) FROM assignments').fetchone()[0]
    def category(self,event,owners):
        from jarvis.household_activities import title_key
        records=self.profile.context().get('confirmed_activity_profiles',[])
        r=next((r for r in records if r['person'] in owners and r['source']=='family' and title_key(r['title'])==title_key(event.get('summary',''))),None)
        if not r:return 'other'
        value=r['activity'].casefold()
        return 'sport' if 'gymnastics' in value else 'music' if any(v in value for v in ('music','orchestra','band')) else 'other'
    async def read(self,start,end,source=CALENDAR):
        if source not in self.allowed:raise ValueError('Calendar is not shared')
        return await asyncio.wait_for(self.client.get_calendar_events(source,start,end),12)
    async def agenda(self,payload):
        self.guard();start=local_time(payload['start'],True);end=local_time(payload['end'],True)
        if not 1<=(end.date()-start.date()).days<=14:raise ValueError('Choose one to fourteen days')
        selected=payload.get('members',[])
        if not isinstance(selected,list) or any(p not in self.people for p in selected):raise ValueError('Unknown household member')
        sources=[CALENDAR]+([s for s in ('calendar.work_reach','calendar.jarvis_travels') if s in self.allowed] if not selected or 'benny' in selected else [])
        async def load(source):
            try:return source,await self.read(start,end,source),None
            except Exception:return source,[],source+' unavailable'
        rows=[];gaps=[];annotations=self.annotations()
        for source,events,error in await asyncio.gather(*(load(s) for s in sources)):
            if error:gaps.append(error);continue
            for event in events:
                if event.get('status')=='cancelled':continue
                from jarvis.household_briefing import interval
                try:parsed=interval(event,event_context=True)
                except (ValueError,KeyError):gaps.append('One appointment has unusable dates');continue
                meta=assignment(event,self.people,annotations,self.ready) if source==CALENDAR else {'members':['benny'],'category':'work' if source=='calendar.work_reach' else 'travel','basis':'connected owner calendar','notes':parsed.get('description','')}
                if selected and not set(selected).intersection(meta['members']):continue
                if parsed['end']<=start or parsed['start']>=end:continue
                category=meta['category'] if meta['category']!='other' else self.category(event,meta['members']) if source==CALENDAR else meta['category']
                rows.append({'key':identity(event),'title':parsed['title'],'start':parsed['start'].isoformat(),'end':parsed['end'].isoformat(),
                    'all_day':parsed['all_day'],'location':parsed.get('location',''),'notes':meta['notes'][:1200],
                    'members':meta['members'],'category':category,'source':source,'basis':meta['basis'],
                    'can_assign':source==CALENDAR and not meta.get('planner_id')})
        rows.sort(key=lambda e:(datetime.fromisoformat(e['start']).timestamp(),e['title'],e['key']))
        return {'schema_version':1,'ready':self.ready,'calendar':CALENDAR,'members':self.project()['members'],'categories':list(CATEGORIES),
            'start':payload['start'],'end':payload['end'],'timezone':'Europe/Oslo','events':rows[:300],
            'source_failures':gaps,'truncated':len(rows)>300,'read_only':True}
    def draft(self,payload):
        self.guard(write=True)
        if set(payload)!={'title','members','category','start','end','all_day','location','notes'}:raise ValueError('Unsupported appointment fields')
        owners=payload['members']
        if not isinstance(owners,list) or not owners or any(not isinstance(o,str) or o not in self.people for o in owners) or len(set(owners))!=len(owners):raise ValueError('Choose the relevant household members')
        if payload['category'] not in CATEGORIES or type(payload['all_day']) is not bool:raise ValueError('Choose a valid category and date type')
        a=local_time(payload['start'],payload['all_day']);b=local_time(payload['end'],payload['all_day'])
        if payload['all_day']:b+=timedelta(days=1) # Form end date is inclusive.
        if not self.now().astimezone(ZONE).date()<=a.date()<=self.now().astimezone(ZONE).date()+timedelta(days=366):raise ValueError('Choose a future date within one year')
        if not 0<b.timestamp()-a.timestamp()<=14*86400+3600:raise ValueError('End must be after start, within fourteen days')
        return {'title':text(payload['title'],160,True),'members':sorted(owners),'category':payload['category'],
            'start':a.date().isoformat() if payload['all_day'] else a.isoformat(),
            'end':b.date().isoformat() if payload['all_day'] else b.isoformat(),'all_day':payload['all_day'],
            'location':text(payload['location'],180),'notes':text(payload['notes'],1200)}
    async def review(self,payload,owner):
        revision=self.profile._data['revision'];clean=self.draft(payload);token=secrets.token_hex(20)
        fingerprint=hashlib.sha256(json.dumps({**{k:clean[k] for k in ('members','start','end','all_day')},'title':self.duplicate_title(clean['title'],clean['members'])},sort_keys=True).encode()).hexdigest()
        existing=await self.read(datetime.fromisoformat(clean['start']).replace(tzinfo=ZONE) if clean['all_day'] else datetime.fromisoformat(clean['start']),
                                 datetime.fromisoformat(clean['end']).replace(tzinfo=ZONE) if clean['all_day'] else datetime.fromisoformat(clean['end']))
        duplicates,overlaps=self.compare(clean,existing)
        if duplicates:return {'state':'duplicate','message':'That appointment is already in Familiekalender. Nothing was added.'}
        other,failures=await self.other_overlaps(clean);overlaps+=other
        if revision!=self.profile._data['revision']:raise ValueError('Household information changed; review again')
        envelope={'draft':clean,'revision':revision,'action':'appointment','overlaps':overlaps,'source_failures':failures}
        with self.db:
            self.db.execute('DELETE FROM intents WHERE state=? AND expires<?',('prepared',self.clock()))
            if self.db.execute("SELECT count(*) FROM intents WHERE state='prepared'").fetchone()[0]>=500:raise ValueError('Too many open reviews; please wait for them to expire')
            self.db.execute('INSERT INTO intents VALUES (?,?,?,?,?,?)',(token,owner,self.clock()+300,fingerprint,json.dumps(envelope),'prepared'))
        return {'state':'review','token':token,'appointment':clean,'overlaps':overlaps,'source_failures':failures,'calendar':CALENDAR,
            'message':'Review the member assignments, dates, times and location before saving. No appointment has been added yet.'}
    def duplicate_title(self,title,members):
        from jarvis.household_activities import title_key,equivalence_key
        record=next((r for r in self.profile._data.get('activity_profiles',[]) if members==[r['person']] and r['source']=='family' and title_key(r['title'])==title_key(title)),None)
        relation=equivalence_key(self.profile._data,record) if record else None
        return ['confirmed-equivalence',*relation] if relation else ['exact-title',title.casefold()]
    async def other_overlaps(self,draft):
        if 'benny' not in draft['members']:return [],[]
        a=datetime.fromisoformat(draft['start']);b=datetime.fromisoformat(draft['end'])
        if draft['all_day']:a=a.replace(tzinfo=ZONE);b=b.replace(tzinfo=ZONE)
        overlaps=[];failures=[]
        for source in ('calendar.work_reach','calendar.jarvis_travels'):
            if source not in self.allowed:continue
            try:
                events=await self.read(a,b,source);_,items=self.compare(draft,events,source=source)
                overlaps.extend({**item,'source':source} for item in items)
            except Exception:failures.append(source+' could not be checked for overlaps')
        return overlaps,failures

    def compare(self,draft,events,source=CALENDAR):
        from jarvis.household_briefing import interval
        a=interval({'start':draft['start'],'end':draft['end'],'summary':draft['title']});duplicates=[];overlaps=[]
        for event in events:
            if event.get('status')=='cancelled':continue
            b=interval(event);members=self.assign(event)['members'] if source==CALENDAR else ['benny']
            if source==CALENDAR and sorted(members)==draft['members'] and self.duplicate_title(b['title'],members)==self.duplicate_title(draft['title'],draft['members']) and (b['start'],b['end'],b['all_day'])==(a['start'],a['end'],a['all_day']):duplicates.append(event)
            elif set(members).intersection(draft['members']) and b['start'].timestamp()<a['end'].timestamp() and b['end'].timestamp()>a['start'].timestamp():
                overlaps.append({'title':b['title'],'start':b['start'].isoformat(),'end':b['end'].isoformat(),'members':members})
        return duplicates,overlaps[:10]
    async def confirm(self,payload,owner):
        self.guard(write=True)
        if set(payload)!={'token'} or not isinstance(payload['token'],str):raise ValueError('Invalid confirmation')
        async with self.lock:
            row=self.db.execute('SELECT owner,expires,fingerprint,payload,state FROM intents WHERE token=?',(payload['token'],)).fetchone()
            if not row or row[0]!=owner:raise ValueError('Review belongs to another session')
            if row[4] in ('confirmed','duplicate'):return {'state':row[4],'message':'Already processed; no second appointment was added.'}
            if row[4]!='prepared':return {'state':'uncertain','message':'The previous save may have reached the calendar. Refresh and check; it will not be sent again automatically.'}
            if row[1]<self.clock():raise ValueError('This review expired; review the appointment again')
            envelope=json.loads(row[3])
            if envelope['revision']!=self.profile._data['revision']:raise ValueError('Household information changed; review again')
            if envelope['action']=='assignment':
                event=await self.find_event(envelope['selection'])
                if self.event_hash(event)!=envelope['source_hash'] or self.annotations().get(envelope['selection']['key'])!=envelope['previous']:
                    raise ValueError('The appointment or its assignment changed; review again')
                self.guard(write=True)
                if envelope['revision']!=self.profile._data['revision']:raise ValueError('Household information changed; review again')
                with self.db:
                    self.db.execute('INSERT INTO assignments VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
                        (envelope['selection']['key'],json.dumps(envelope['assignment'])))
                    self.db.execute("UPDATE intents SET state='confirmed' WHERE token=?",(payload['token'],))
                return {'state':'confirmed','message':'Member/category assignment saved in Jarvis. The Google appointment itself is unchanged.'}
            draft=envelope['draft'];a=datetime.fromisoformat(draft['start']);b=datetime.fromisoformat(draft['end'])
            if draft['all_day']:a=a.replace(tzinfo=ZONE);b=b.replace(tzinfo=ZONE)
            existing=await self.read(a,b);duplicates,_=self.compare(draft,existing)
            if duplicates:
                with self.db:self.db.execute("UPDATE intents SET state='duplicate' WHERE token=?",(payload['token'],))
                return {'state':'duplicate','message':'That appointment now exists. Nothing was added.'}
            _,overlaps=self.compare(draft,existing);other,failures=await self.other_overlaps(draft);overlaps+=other
            if overlaps!=envelope['overlaps'] or failures!=envelope['source_failures']:
                raise ValueError('Overlap information changed; review the appointment again')
            self.guard(write=True)
            if envelope['revision']!=self.profile._data['revision']:raise ValueError('Household information changed; review again')
            prior=self.db.execute("SELECT state FROM intents WHERE fingerprint=? AND state IN ('sending','uncertain','confirmed')",(row[2],)).fetchone()
            if prior:return {'state':'uncertain','message':'An identical save was already attempted. Check the calendar before doing anything further.'}
            data={'entity_id':CALENDAR,'summary':draft['title'],'description':description(draft['members'],draft['category'],payload['token'],draft['notes'])}
            data.update({'start_date' if draft['all_day'] else 'start_date_time':draft['start'],'end_date' if draft['all_day'] else 'end_date_time':draft['end']})
            if draft['location']:data['location']=draft['location']
            with self.db:self.db.execute("UPDATE intents SET state='sending' WHERE token=?",(payload['token'],))
            try:
                await asyncio.wait_for(self.client.create_household_appointment(data),12)
                actual=await self.read(a,b)
                if not any(self.assign(e).get('planner_id')==payload['token'] for e in actual):raise ValueError('Save not visible yet')
            except Exception:
                with self.db:self.db.execute("UPDATE intents SET state='uncertain' WHERE token=?",(payload['token'],))
                return {'state':'uncertain','message':'Save outcome is not confirmed. Refresh and check the calendar; no automatic retry will occur.'}
            with self.db:self.db.execute("UPDATE intents SET state='confirmed' WHERE token=?",(payload['token'],))
            return {'state':'confirmed','message':'Saved to Familiekalender for '+', '.join(self.people[p] for p in draft['members'])+'.'}

    @staticmethod
    def event_hash(event):return hashlib.sha256(json.dumps(event,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

    async def find_event(self,selection):
        if set(selection)!={'key','start','end'}:raise ValueError('Invalid appointment selection')
        a=local_time(selection['start'],True);b=local_time(selection['end'],True)
        if not 0<(b.date()-a.date()).days<=14:raise ValueError('Select one appointment within fourteen days')
        events=await self.read(a,b);matches=[e for e in events if e.get('status')!='cancelled' and identity(e)==selection['key']]
        if len(matches)!=1:raise ValueError('The appointment changed or is ambiguous; refresh the agenda')
        return matches[0]

    async def review_assignment(self,payload,owner):
        self.guard(write=True);revision=self.profile._data['revision']
        if set(payload)!={'key','start','end','members','category'}:raise ValueError('Invalid assignment fields')
        members=payload['members']
        if not isinstance(members,list) or not members or any(not isinstance(p,str) or p not in self.people for p in members) or len(set(members))!=len(members) or payload['category'] not in CATEGORIES:raise ValueError('Choose members and a category')
        selection={k:payload[k] for k in ('key','start','end')};event=await self.find_event(selection)
        if revision!=self.profile._data['revision']:raise ValueError('Household information changed; review again')
        if self.assign(event).get('planner_id'):raise ValueError('This appointment already carries its assignment in Google Calendar; edit its original planner metadata there')
        assignment_value={'members':sorted(members),'category':payload['category']};token=secrets.token_hex(20)
        envelope={'action':'assignment','revision':revision,'selection':selection,'source_hash':self.event_hash(event),
            'previous':self.annotations().get(selection['key']),'assignment':assignment_value}
        with self.db:
            self.db.execute('DELETE FROM intents WHERE state=? AND expires<?',('prepared',self.clock()))
            if self.db.execute("SELECT count(*) FROM intents WHERE state='prepared'").fetchone()[0]>=500:raise ValueError('Too many open reviews; please wait for them to expire')
            self.db.execute('INSERT INTO intents VALUES (?,?,?,?,?,?)',(token,owner,self.clock()+300,token,json.dumps(envelope),'prepared'))
        return {'state':'review_assignment','token':token,'title':event.get('summary','Appointment'),'assignment':assignment_value,
            'message':'Review the assignment. This changes the Jarvis catalogue, not the appointment time or Google notes.'}

    async def request(self,action,payload,owner):
        if not isinstance(payload,dict) or not isinstance(owner,str) or not 1<=len(owner)<=200:raise ValueError('Invalid planner request')
        if action=='agenda':return await self.agenda(payload)
        if action=='review':return await self.review(payload,owner)
        if action=='assign_review':return await self.review_assignment(payload,owner)
        if action=='confirm':return await self.confirm(payload,owner)
        raise ValueError('Unsupported planner operation')

def get_planner(container):
    planner=getattr(container,'household_planner',None)
    if planner is None:
        profile=container.household_profile
        source=getattr(profile,'_source_path',None)
        planner=HouseholdPlanner(profile,container.home_assistant,getattr(container,'proactive_allowed_entities',()),
            path=Path(source).parent/'household_planner.sqlite3' if source else None)
        container.household_planner=planner
    return planner
