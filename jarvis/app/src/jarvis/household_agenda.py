"""Opted-in read-only preparation, refreshed from calendars while Jarvis is idle.

Plans are disposable projections, not memories or commitments. Only the separate
explicit approval is durable. Foreground questions cancel work; source changes
withdraw old plans before replacement prose can be published.
"""
import asyncio,json
from copy import deepcopy
from datetime import datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from jarvis.household_briefing import Brief
from jarvis.household_speaker import shared_knowledge_enabled
from jarvis.companion_store import digest,secret,instruction_attempt
from jarvis.event_preparation import EventPreparation,safe_detail
from jarvis.calendar_insights import appointment_label
from jarvis.activity_departure import checked_journey

ZONE=ZoneInfo('Europe/Oslo')

class Superseded(Exception):pass

class HouseholdAgenda:
 def __init__(self,owner,*,approval=None):
  self.owner=owner;self.approval=approval;self.records={};self.routes={}
  self.source_health={};self.task=None;self.work=None;self.last_scan=-1000.;self.status='not_checked';self.checked_at=None
 def enabled(self):
  try:
   data=self.approval
   if data is None:
    source=getattr(self.owner.profile,'_source_path',None)
    if source is None:return False
    data=json.loads(source.with_name('household_planning_policy.json').read_text(encoding='utf-8'))
   return (set(data)=={'schema_version','enabled','approval_source','recorded_on'} and data['schema_version']==1
    and data['enabled'] is True and bool(data['approval_source']) and datetime.fromisoformat(data['recorded_on']).date()
    and self.owner.policy.data['enabled'] and shared_knowledge_enabled(self.owner.profile._data))
  except (ValueError,TypeError,KeyError,OSError):return False
 def binding(self):
  return (self.owner.profile._data['revision'],self.owner.now().astimezone(ZONE).date().isoformat(),
   tuple(sorted(getattr(self.owner.container,'proactive_allowed_entities',()))),digest(self.owner.policy.data),self.owner.store.generation)
 def valid(self,binding):
  if self.owner.foreground or not self.enabled() or binding!=self.binding():raise Superseded()
 def start(self):
  if self.task is None:self.task=asyncio.create_task(self.run())
 def interrupt(self):
  if self.work and not self.work.done():self.work.cancel()
 async def close(self):
  self.interrupt()
  if self.task:self.task.cancel()
  await asyncio.gather(*(t for t in (self.task,self.work) if t),return_exceptions=True)
 async def run(self):
  while True:
   await asyncio.sleep(2)
   if not self.enabled():self.status='disabled';self.records.clear();continue
   if self.owner.foreground or self.owner.clock()-self.owner.last_activity<10 or self.owner.clock()-self.last_scan<60:continue
   self.last_scan=self.owner.clock();self.work=asyncio.create_task(self.refresh())
   try:await self.work
   except asyncio.CancelledError:
    if asyncio.current_task().cancelling():raise
   except Exception:self.status='needs_check';self.records.clear()
   finally:self.work=None
 async def refresh(self):
  if not self.enabled():self.status='disabled';self.records.clear();return
  from jarvis.household_planner import get_planner
  get_planner(self.owner.container) # Load the shared member catalogue before any calendar ownership is read.
  binding=self.binding();self.valid(binding);today=self.owner.now().astimezone(ZONE).date()
  reader=getattr(self.owner.container,'household_thinking',None)
  if reader is None or tuple(sorted(reader.reader.allowed))!=binding[2]:self.status='needs_check';self.records.clear();return
  self.status='preparing';people={m['id']:m['preferred_name'] for m in self.owner.profile._data['members']}
  for offset in (0,1):
   day=today+timedelta(days=offset);start=day.isoformat();end=(day+timedelta(days=1)).isoformat()
   stage='calendar'
   try:
    loaded=await asyncio.wait_for(reader.reader.handle('household preparation',None,resolved=Brief('all',start,end),structured_only=True,targets=tuple(people),event_context=True),15)
    self.valid(binding)
    if not loaded or loaded.get('status')!='success':raise ValueError('Calendar read unavailable')
    evidence=loaded['evidence'];self.source_health=evidence.get('source_health',{});stage='planning';fingerprint=self.fingerprint(binding,evidence)
    old=self.records.get(start)
    if old and old.get('fingerprint')==fingerprint and self.owner.clock()-old['built_at']<1800:
     old['checked_at']=self.owner.now().isoformat();old['source_health']=deepcopy(self.source_health);continue
    # No old event/time remains on screen once a changed source is observed.
    self.records[start]={'date':start,'state':'preparing','people':[],'binding':binding}
    rows=[]
    for person,name in people.items():
     self.valid(binding)
     row=await self.person_plan(person,name,evidence,binding)
     self.valid(binding);rows.append(row)
    again=await asyncio.wait_for(reader.reader.handle('household preparation recheck',None,resolved=Brief('all',start,end),structured_only=True,targets=tuple(people),event_context=True),15)
    self.valid(binding)
    if not again or again.get('status')!='success' or self.fingerprint(binding,again['evidence'])!=fingerprint:raise Superseded()
    self.records[start]={'date':start,'label':'Today' if not offset else 'Tomorrow','state':'partial' if evidence['source_failures'] or evidence['truncated'] else 'ready',
     'people':rows,'source_health':deepcopy(self.source_health),'coordination':self.coordination(evidence,people),'coverage':'Some calendar information could not be checked; these plans may be incomplete.' if evidence['source_failures'] or evidence['truncated'] else 'Connected calendar plans; routines are usual, not confirmed attendance.',
     'fingerprint':fingerprint,'built_at':self.owner.clock(),'binding':binding,'checked_at':self.owner.now().isoformat()}
   except Superseded:raise
   except asyncio.CancelledError:raise
   except Exception:
    self.records[start]={'date':start,'state':'needs_check','people':[],'binding':binding,'failure_kind':stage,'source_health':deepcopy(self.source_health),'coverage':'Calendar information needs checking. Previous plans are withheld.' if stage=='calendar' else 'The calendar was checked, but the plan could not be prepared. Previous advice is withheld.'}
  self.valid(binding);self.checked_at=self.owner.now().isoformat();self.status='ready' if all(r['state']=='ready' for r in self.records.values()) else 'partial'
  self.records={d:r for d,r in self.records.items() if d in (today.isoformat(),(today+timedelta(days=1)).isoformat())}
  self.routes={k:v for k,v in self.routes.items() if self.owner.clock()-v[0]<1800}
 def coordination(self,evidence,people):
  events=[f for f in evidence['facts'] if f['kind']=='appointment' and not f['all_day'] and datetime.fromisoformat(f['end'])>self.owner.now()]
  remarks=[]
  for i,a in enumerate(events):
   for b in events[i+1:]:
    if set(a['owners']).intersection(b['owners']) or not a.get('location') or not b.get('location') or a['location'].casefold().strip()==b['location'].casefold().strip():continue
    if datetime.fromisoformat(a['start'])<datetime.fromisoformat(b['end']) and datetime.fromisoformat(b['start'])<datetime.fromisoformat(a['end']):
     names=' and '.join(people[p] for p in dict.fromkeys(a['owners']+b['owners']))
     remarks.append(names+' have overlapping calendar appointments at different listed venues. If shared transport is needed, confirm who can help.')
  return list(dict.fromkeys(remarks))[:3]
 def fingerprint(self,binding,evidence):
  now=self.owner.now()
  phases=[(f['id'],datetime.fromisoformat(f['start'])<=now,datetime.fromisoformat(f['end'])<=now) for f in evidence['facts'] if f['kind']=='appointment']
  return digest([binding,evidence['facts'],evidence['source_failures'],evidence['truncated'],phases])
 async def person_plan(self,person,name,evidence,binding):
  now=self.owner.now().astimezone(ZONE);facts=[deepcopy(f) for f in evidence['facts'] if person in f['owners']]
  events=[f for f in facts if f['kind']=='appointment' and (f['all_day'] or datetime.fromisoformat(f['end'])>now)]
  for event in events:
   if not safe_detail(event['text']):event['text']='a recorded appointment';event.pop('confirmed_activity',None)
  events.sort(key=lambda e:e['start']);routines=[f['text'] for f in facts if f['kind']=='routine' and safe_detail(f['text'])][:2]
  selected_ids={e['id'] for e in events}
  current=evidence['start']==now.date().isoformat()
  summary=('No further appointments are listed for '+name+' today in the connected calendars; other plans may exist.' if current else 'No appointments are listed for '+name+' on this date in the connected calendars; other plans may exist.')
  if evidence['source_failures'] or evidence['truncated']:summary='The calendar view is incomplete, so I cannot rule out other appointments.'
  if events:summary=' '.join((appointment_label(e)+' ('+('all day' if e['all_day'] else e['local_start'])+').') for e in events[:6])
  from jarvis.household_thinking import HouseholdThinking
  family=any(e['source']=='family' for e in events)
  engine=(EventPreparation if family else HouseholdThinking)(self.owner.profile,self.owner.container.home_assistant,binding[2],self.owner.background,now=self.owner.now)
  scoped={**deepcopy(evidence),'people':{person:name},'facts':[f for f in facts if f['kind']!='appointment' or f['id'] in selected_ids]}
  class Frozen:
   async def handle(self,*args,**kwargs):return {'status':'success','evidence':deepcopy(scoped)}
  engine.reader=Frozen();out=None
  try:
   if not events:raise ValueError('No remaining appointments need model composition')
   question=('What should '+name+' prepare for ' if family else 'What does '+name+' have on ')+evidence['start']+'?'
   out=await asyncio.wait_for(engine.handle(question,None,**({} if family else {'tool_selected':True})),20)
   self.valid(binding)
   if out and out.get('status')=='success':summary=out['message']
  except (ValueError,asyncio.TimeoutError):pass
  attention=[]
  for f in facts:
   if f['kind']=='overlap' and safe_detail(f['text']) and datetime.fromisoformat(f['date']+'T'+f['local_end']).replace(tzinfo=ZONE)>now:attention.append(f['text']+'. Check whether both commitments apply.')
  for first,second in zip([e for e in events if not e['all_day']],[e for e in events if not e['all_day']][1:]):
   gap=int((datetime.fromisoformat(second['start'])-datetime.fromisoformat(first['end'])).total_seconds()/60)
   if 0<=gap<=60:attention.append('The recorded gap before '+appointment_label(second)+' is '+str(gap)+' minutes; journeys and getting ready still need allowing for.')
  departures=[];attempts=0
  for event in events:
   if event['source']!='family' or event['all_day'] or datetime.fromisoformat(event['start'])<=now:continue
   if attempts>=4:attention.append('Further journeys have not been checked in this brief.');break
   attempts+=1;self.valid(binding)
   try:
    key=digest([event,self.owner.profile._data.get('activity_profiles',[]),binding])
    cached=self.routes.get(key)
    if cached and self.owner.clock()-cached[0]<1800:journey=cached[1]
    else:
     journey=await asyncio.wait_for(checked_journey(self.owner,event,10),24);self.valid(binding);self.routes[key]=(self.owner.clock(),journey)
    if journey:
     leave=datetime.fromisoformat(event['start'])-timedelta(minutes=journey['minutes']+10)
     venue=journey['venue'];basis='Entur driving estimate' if journey['basis']=='Entur' else 'saved usual user estimate'
     text='If leaving from home for '+appointment_label(event)+', aim for '+leave.astimezone(ZONE).strftime('%H:%M')+' ('+str(journey['minutes'])+' minutes, '+basis+', plus a 10-minute planning allowance).'
     if venue.get('usual_venue'):text+=' This uses the usual venue; check the current appointment location.'
     text+=' Not live traffic; no driver is assigned.'
     departures.append({'event':event['text'],'leave_at':leave.astimezone(ZONE).isoformat(),'text':text,'basis':journey['basis'],'minutes':journey['minutes'],'allowance_minutes':10})
    else:attention.append('The venue or journey for '+appointment_label(event)+' still needs checking before a departure time can be suggested.')
   except (ValueError,KeyError,TypeError,asyncio.TimeoutError):attention.append('The journey for '+appointment_label(event)+' could not be checked just now.')
  self.valid(binding)
  return {'id':person,'name':name,'summary':summary,'routines':routines,'attention':list(dict.fromkeys(attention))[:6],'departures':departures,'event_count':len(events),'model_composed':bool(out and (out.get('language_model_composition') or out.get('local_model_interpretation')))}
 def project(self):
  if not self.enabled():return {'status':'disabled','days':[],'read_only':True}
  binding=self.binding();today=self.owner.now().astimezone(ZONE).date();days=[]
  for offset in (0,1):
   date=(today+timedelta(days=offset)).isoformat();row=self.records.get(date)
   if not row or tuple(row.get('binding',()))!=binding:continue
   item={k:deepcopy(v) for k,v in row.items() if k not in ('binding','fingerprint','built_at')}
   item['label']='Today' if offset==0 else 'Tomorrow'
   checked=row.get('checked_at')
   if not checked or (self.owner.now()-datetime.fromisoformat(checked)).total_seconds()>180:
    item.update(state='needs_check',people=[],coverage=row.get('coverage') if row['state']=='needs_check' else 'Calendar refresh is pending; previous plans are withheld.')
   for person in item.get('people',[]):
    for departure in person.get('departures',[]):
     if datetime.fromisoformat(departure['leave_at'])<=self.owner.now():departure['text']='The suggested home departure time has passed; recheck the journey before setting off. '+departure['text']
   days.append(item)
  from jarvis.calendar_freshness import current_health
  return {'status':self.status,'checked_at':self.checked_at,'days':days,'source_health':current_health(self.source_health,self.owner.now()),'read_only':True,'refresh_interval_seconds':60}
