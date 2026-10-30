"""Shared, source-bound planning gaps and explicit preparation follow-through.

No autonomous writes: Qwen only extracts bounded user quotes. A fresh selected
appointment, HA permissions and explicit review/confirmation own each save.
"""
import asyncio,json,re,secrets
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from jarvis.companion_store import digest,bounded,secret,instruction_attempt,stamp
from jarvis.household_planner import ZONE,CALENDAR,get_planner
from jarvis.household_activities import safe,title_key
from jarvis.calendar_freshness import collect,SOURCES,current_health
from jarvis.planning_reports import PlanningReports
from jarvis.planning_followup_model import extract,details_after
SOURCE_NAMES={value[0]:key for key,value in SOURCES.items()}
class PlanningFollowups:
 def __init__(self,owner):
  self.owner=owner;self.reports=PlanningReports(owner.store);self.items={};self.sessions={};self.checked_at=None;self.checked_clock=-1000.;self.status='preparing';self.source_health={};self.failures=[];self.task=None;self.work=None;self.binding=None
 def enabled(self):return bool(self.owner.policy.data['enabled'] and self.owner.agenda.enabled())
 def scope(self):return (self.owner.profile._data['revision'],tuple(sorted(self.owner.container.proactive_allowed_entities)),self.owner.now().astimezone(ZONE).date().isoformat(),self.owner.store.generation,self.reports.revision)
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
   if not self.enabled():self.items.clear();self.status='disabled';continue
   if self.owner.foreground or self.owner.clock()-self.owner.last_activity<10 or self.owner.clock()-self.checked_clock<60:continue
   self.checked_clock=self.owner.clock();self.work=asyncio.create_task(self.refresh())
   try:await self.work
   except asyncio.CancelledError:
    if asyncio.current_task().cancelling():raise
   except Exception:self.items.clear();self.status='needs_check'
   finally:self.work=None
 async def load(self,start,end,person=None):
  planner=get_planner(self.owner.container);allowed=set(self.owner.container.proactive_allowed_entities)
  names=[n for n,v in SOURCES.items() if v[0] in allowed]
  health=await collect(self.owner.container.home_assistant,names,self.owner.now())
  data=await planner.agenda({'start':start,'end':end,'members':[person] if person else []},enrich=False)
  blocked={row['entity_id'] for row in health.values() if row['status'] not in ('fresh','not_configured')}
  rows=[e for e in data['events'] if e['source'] not in blocked and datetime.fromisoformat(e['end'])>self.owner.now()]
  return rows,health,list(data['source_failures'])+['Calendar refresh needs checking' for _ in blocked],data['truncated']
 async def refresh(self):
  if not self.enabled():self.items={};self.status='disabled';return
  scope=self.scope();today=self.owner.now().astimezone(ZONE).date()
  rows,health,failures,truncated=await self.load(today.isoformat(),(today+timedelta(days=7)).isoformat())
  if scope!=self.scope() or not self.enabled():return
  items={}
  for e in rows[:60]:
   if not safe(e['title'],160):continue
   for person in e['members'] or [None]:
    item=self.build(e,person)
    if item['gaps'] or item['checklist'] or item.get('report'):items[item['id']]=item
  self.items=items;self.source_health=health;self.failures=failures+(['Some appointments are outside this brief'] if truncated else []);self.binding=scope;self.checked_at=self.owner.now().isoformat();self.checked_clock=self.owner.clock();self.status='partial' if self.failures else 'ready'
  self.sessions={k:v for k,v in self.sessions.items() if v['expires']>self.owner.clock()}
 def build(self,event,person):
  source=SOURCE_NAMES[event['source']];version=digest({k:event[k] for k in ('key','title','start','end','all_day','members','location','notes')})[:20]
  key='P'+digest([event['source'],event['key'],person])[:14];date=datetime.fromisoformat(event['start']).astimezone(ZONE).date().isoformat()
  usual=next((r for r in self.owner.profile._data.get('activity_profiles',[]) if r['person']==person and r['source']==source and title_key(r['title'])==title_key(event['title'])),None)
  item={'id':key,'version':version,'title':event['title'],'person':person,'name':next((p['preferred_name'] for p in self.owner.profile._data['members'] if p['id']==person),'Unassigned'),'source':event['source'],'date':date,'start':event['start'],'end':event['end'],'all_day':event['all_day'],'category':event['category'],'calendar_writable':event['source']==CALENDAR,'gaps':[],'checklist':[],'_event':deepcopy(event),'_usual':deepcopy(usual)}
  report=self.reports.get(item);details=(report or {}).get('details',{})
  current=event['location'];reported=details.get('venue');item['venue']=current or reported or (usual or {}).get('usual_venue') or ''
  item['venue_basis']='calendar' if current else 'reported for this appointment' if reported else 'usual venue' if item['venue'] else 'unknown'
  online=bool(re.search(r'teams\.microsoft|teams\.live|zoom\.us|online meeting',event['notes'],re.I))
  if not person:item['gaps'].append('person')
  if not item['venue'] and not online:item['gaps'].append('venue')
  if current and reported and title_key(current)!=title_key(reported):item['gaps'].append('venue_conflict')
  equipment=details.get('equipment',(usual or {}).get('equipment',[]));preparation=details.get('preparation',(usual or {}).get('preparation'))
  if event['category'] in ('sport','music') and not equipment and not preparation and not event['notes']:item['gaps'].append('preparation')
  def step(kind,label,basis):
   if not safe(label,300):return
   sid='C'+digest([kind,label])[:12];item['checklist'].append({'id':sid,'text':label,'basis':basis,'ready':sid in (report or {}).get('checked',[])})
  for value in equipment[:12]:step('equipment',value,'reported for this appointment' if 'equipment' in details else 'usual equipment; check organiser notes')
  if preparation:step('preparation',preparation,'reported for this appointment' if 'preparation' in details else 'usual preparation; check organiser notes')
  if event['notes']:step('organiser','Review the organiser notes','calendar notes; requirements are not inferred')
  item['report']=({k:report[k] for k in ('recorded_at','quote','basis')} if report else None)
  item['state']='needs_details' if item['gaps'] else 'resolved' if not item['checklist'] else 'reported_ready' if item['checklist'] and all(s['ready'] for s in item['checklist']) else 'preparation'
  return item
 def public(self,item):return {k:deepcopy(v) for k,v in item.items() if not k.startswith('_')}
 def project(self):
  if not self.enabled():return {'status':'disabled','items':[],'read_only':True}
  valid=self.binding==self.scope() and self.owner.clock()-self.checked_clock<=180 and all(v['status'] in ('fresh','not_configured') for v in current_health(self.source_health,self.owner.now()).values())
  return {'status':self.status if valid else 'preparing','checked_at':self.checked_at,'items':[self.public(v) for v in self.items.values()] if valid else [],'source_failures':list(self.failures) if valid else [],'source_health':current_health(self.source_health,self.owner.now()),'read_only':True,'report_basis':'Readiness is household-reported, never attendance or location.'}
 async def resolve(self,item_id,version):
  if not self.enabled():raise ValueError('Household planning is paused')
  item=self.items.get(item_id)
  if item is None or item['version']!=version:raise ValueError('That appointment changed or left this brief. Refresh and choose it again.')
  today=self.owner.now().astimezone(ZONE).date();day=datetime.fromisoformat(item['date']).date()
  if not today<=day<today+timedelta(days=7):raise ValueError('Choose a current appointment in the next seven days')
  rows,_,failures,_=await self.load(day.isoformat(),(day+timedelta(days=1)).isoformat(),item['person'])
  found=[self.build(e,item['person']) for e in rows if e['source']==item['source'] and e['key']==item['_event']['key'] and (not item['person'] or item['person'] in e['members'])]
  if len(found)!=1 or found[0]['version']!=version:raise ValueError('The appointment changed, was cancelled or cannot be checked. Refresh before continuing.')
  return found[0]
 def question(self,item):
  gap=(item['gaps'] or ['checklist'])[0]
  return {'person':'Who is this appointment for?','venue':'Where will this appointment take place?','venue_conflict':'Your reported venue differs from the calendar. Which location should be corrected?','preparation':'What does '+item['name']+' need to bring or prepare?','checklist':'What is ready, or which detail would you like to clarify?'}[gap]
 async def open(self,item_id,version,owner):
  item=await self.resolve(item_id,version);token=secrets.token_hex(18)
  if len(self.sessions)>=128:raise ValueError('Too many open planning conversations. Close one or wait for it to expire.')
  self.sessions[token]={'owner':owner,'item':item_id,'version':version,'binding':self.scope(),'expires':self.owner.clock()+1200,'pending':None,'lock':asyncio.Lock()}
  return {'state':'conversation','session':token,'item':self.public(item),'message':self.question(item)}
 def session(self,token,owner):
  value=self.sessions.get(token)
  if not value or value['owner']!=owner or value['expires']<=self.owner.clock():raise ValueError('That focused conversation expired. Open the appointment again.')
  if value['binding']!=self.scope():raise ValueError('The household context changed. Reopen the appointment before saving.')
  return value
 def summary(self,details):
  lines=[]
  if details.get('venue'):lines.append('Venue: '+details['venue'])
  if 'equipment' in details:lines.append('Equipment: '+(', '.join(details['equipment']) or 'none recorded'))
  if details.get('preparation'):lines.append('Preparation: '+details['preparation'])
  if details.get('journey_minutes'):lines.append('Home journey: '+str(details['journey_minutes'])+' minutes (your estimate)')
  return lines
 async def answer(self,token,owner,text,*,scope=None,active_step=None):
  session=self.session(token,owner)
  async with session['lock']:
   item=await self.resolve(session['item'],session['version']);self.cancel_pending(session)
   frame=await extract(self.owner,item,text,active_step,scope);self.session(token,owner)
   await self.resolve(session['item'],session['version'])
   if frame['intent'] in ('unrelated','unclear') or frame['scope']=='unclear':return {'state':'conversation','session':token,'item':self.public(item),'message':frame['question'] or 'Please give the detail for this appointment, or use Ask Jarvis for another topic.'}
   pending={'token':secrets.token_hex(18),'kind':frame['intent'],'frame':frame,'quote':text,'expires':self.owner.clock()+300,'item':deepcopy(item),'scope':frame['scope'],'report_digest':digest(self.reports.get(item))}
   if not item['person']:
    if not frame['member']:return {'state':'conversation','session':token,'item':self.public(item),'message':'Please name the household member this appointment is for.'}
    if item['source']!=CALENDAR:raise ValueError('Please correct the attendee in the source calendar')
    planner=get_planner(self.owner.container);day=datetime.fromisoformat(item['date']).date()
    review=await planner.review_assignment({'key':item['_event']['key'],'start':day.isoformat(),'end':(day+timedelta(days=1)).isoformat(),'members':[frame['member']],'category':item['category']},owner)
    pending.update(kind='assignment',native_token=review['token']);lines=['Assign this appointment to '+next(p['preferred_name'] for p in self.owner.profile._data['members'] if p['id']==frame['member'])+'. The Google appointment itself is unchanged. Other details in this reply have not been saved; reopen the assigned appointment to review them.']
   elif frame['intent']=='clear':lines=['Remove the dated preparation report for this appointment. Usual activity knowledge and calendar details stay unchanged.']
   elif frame['scope']=='usual' and frame['intent']=='details':
    details=details_after({},frame,item['_usual']);record=deepcopy(item['_usual']) if item['_usual'] else {'id':secrets.token_hex(4),'person':item['person'],'source':SOURCE_NAMES[item['source']],'title':item['title'],'activity':item['title'],'equipment':[],'preparation':None,'usual_venue':None,'duration_minutes':None,'recorded_on':stamp(self.owner.now()),'provenance':'Confirmed shared household conversation'}
    if details.get('venue') and record['usual_venue']!=details['venue']:record.pop('home_journey',None)
    if 'venue' in details:record['usual_venue']=details['venue']
    if 'equipment' in details:record['equipment']=details['equipment']
    if 'preparation' in details:record['preparation']=details['preparation']
    if 'journey_minutes' in details:record['home_journey']={'minutes':details['journey_minutes'],'quote':details['journey_quote'],'recorded_on':stamp(self.owner.now()),'venue':record['usual_venue']}
    record.update(recorded_on=stamp(self.owner.now()),learning_quote=text)
    profile_key='planning-followup:'+token
    proposed=await asyncio.to_thread(self.owner.profile._edits.propose_activity_record,record,profile_key,'; '.join(self.summary(details)))
    if proposed.get('status')!='clarification_required' or profile_key not in self.owner.profile._edits.pending:raise ValueError('The usual details could not be prepared for confirmation.')
    pending.update(kind='usual',profile_key=profile_key);lines=['Save usual activity knowledge for '+item['name']+'; this does not edit any calendar occurrence.',*self.summary(details)]
   else:
    previous=self.reports.get(item) or {};details=details_after(previous.get('details'),frame,item['_usual']);checked=set(previous.get('checked',[]));checked.update(frame['ready']);checked.difference_update(frame['not_ready']);pending.update(kind='report',details=details,checked=sorted(checked))
    lines=['Use this household-reported information for this appointment only. The phone calendar is unchanged.',*self.summary(details)]
    if frame['ready']:lines.append('Reported ready: '+', '.join(s['text'] for s in item['checklist'] if s['id'] in frame['ready'])+'. This does not confirm attendance.')
    if frame['not_ready']:lines.append('Not ready: '+', '.join(s['text'] for s in item['checklist'] if s['id'] in frame['not_ready'])+'.')
    if details==previous.get('details',{}) and sorted(checked)==sorted(previous.get('checked',[])):return {'state':'conversation','session':token,'item':self.public(item),'message':'I did not find a new preparation detail or readiness change to save.'}
   session['pending']=pending
   return {'state':'review','session':token,'token':pending['token'],'scope':pending['scope'],'kind':pending['kind'],'lines':lines,'message':'Review before confirming. Nothing has been saved yet.'}
 async def calendar_review(self,token,owner,venue):
  session=self.session(token,owner)
  async with session['lock']:
   item=await self.resolve(session['item'],session['version'])
   if item['source']!=CALENDAR:raise ValueError('Change that location in its source calendar; this connection is read-only.')
   if not safe(venue,180):raise ValueError('Please provide a plain venue name')
   self.cancel_pending(session)
   from jarvis.calendar_changes import review
   day=datetime.fromisoformat(item['date']).date()
   result=await review(get_planner(self.owner.container),{'key':item['_event']['key'],'start':day.isoformat(),'end':(day+timedelta(days=1)).isoformat()},'update',{'location':venue},owner)
   self.session(token,owner);await self.resolve(session['item'],session['version'])
   if result['state']!='review_change':return result
   pending={'token':secrets.token_hex(18),'kind':'calendar','native_token':result['token'],'scope':'calendar','expires':self.owner.clock()+300}
   session['pending']=pending
   return {'state':'review','session':token,'token':pending['token'],'kind':'calendar','scope':'calendar','lines':['Change the Household calendar location for this occurrence to '+venue+'.','This updates the appointment shown on your phone. Recurring future occurrences and usual knowledge stay unchanged.',*(['Check possible overlapping appointments before confirming.'] if result.get('overlaps') else [])],'message':'Review the source-calendar change before confirming.'}
 def cancel_pending(self,session):
  pending=session.get('pending')
  if pending and pending.get('profile_key'):self.owner.profile._edits.pending.pop(pending['profile_key'],None)
  session['pending']=None
 async def confirm(self,token,owner,review_token):
  session=self.session(token,owner)
  async with session['lock']:
   pending=session.get('pending')
   if not pending or pending['token']!=review_token or pending['expires']<=self.owner.clock():raise ValueError('That review expired. Please review the detail again.')
   if pending.get('result'):return deepcopy(pending['result'])
   item=await self.resolve(session['item'],session['version']);self.session(token,owner)
   if pending.get('report_digest') and pending['report_digest']!=digest(self.reports.get(item)):raise ValueError('Another preparation report changed after this review. Review it again before saving.')
   kind=pending['kind']
   if kind=='sending':return {'state':'uncertain','message':'That save may already have been sent. Refresh and check; it will not be automatically retried.'}
   pending['kind']='sending'
   try:
    if kind=='usual':
     result=await asyncio.to_thread(self.owner.profile.edit_request,'confirm household change',pending['profile_key'])
     if result.get('status')!='success':raise ValueError('The usual activity change was not confirmed. Review it again.')
     message='Saved the confirmed usual activity details for '+item['name']+'.'
    elif kind in ('assignment','calendar'):
     result=await get_planner(self.owner.container).confirm({'token':pending['native_token']},owner)
     if result.get('state')!='confirmed':raise ValueError('The member assignment was not confirmed. Refresh and check.')
     message=result['message']
    elif kind=='clear':self.reports.clear(item);message='Removed the dated preparation report. Calendar and usual details are unchanged.'
    elif kind=='report':
     self.reports.save(item,pending['details'],pending['checked'],pending['quote'],owner);message='Saved this appointment’s household-reported preparation details. The calendar is unchanged.'
    else:raise ValueError('Unsupported planning confirmation')
   except Exception:
    pending['kind']='sending';raise
   self.owner.agenda.last_scan=-1000.
   session['binding']=self.scope();session['expires']=self.owner.clock()+1200
   try:await self.refresh()
   except Exception:self.items={};self.status='needs_check'
   new_item=self.items.get(item['id']);result={'state':'confirmed','session':token,'message':message,'item':self.public(new_item) if new_item else None,'queue':self.project()};pending['result']=deepcopy(result);return result
 async def ui_request(self,payload,owner):
  if not isinstance(payload,dict) or 'followup_operation' not in payload:raise ValueError('Invalid focused planning request')
  operation=payload['followup_operation'];allowed={'list':{'followup_operation'},'open':{'followup_operation','item','version'},'answer':{'followup_operation','session','text','scope','active_step'},'confirm':{'followup_operation','session','token'},'cancel':{'followup_operation','session'},'calendar_review':{'followup_operation','session','venue'}}
  if not isinstance(operation,str) or operation not in allowed or set(payload)-allowed[operation]:raise ValueError('Unsupported focused planning fields')
  required={'list':set(),'open':{'item','version'},'answer':{'session','text'},'confirm':{'session','token'},'cancel':{'session'},'calendar_review':{'session','venue'}}
  if not required[operation].issubset(payload):raise ValueError('Missing focused planning fields')
  for field,maximum in (('item',80),('version',80),('session',80),('token',80),('text',700),('venue',180),('active_step',40),('scope',20)):
   if field in payload and (not isinstance(payload[field],str) or not 1<=len(payload[field])<=maximum):raise ValueError('Invalid focused planning field')
  self.owner.enter()
  try:
   get_planner(self.owner.container).guard(write=True)
   if operation=='list':await self.refresh();return self.project()
   if operation=='open':return await self.open(payload['item'],payload['version'],owner)
   if operation=='answer':return await self.answer(payload['session'],owner,payload['text'],scope=payload.get('scope'),active_step=payload.get('active_step'))
   if operation=='calendar_review':return await self.calendar_review(payload['session'],owner,payload['venue'])
   if operation=='confirm':return await self.confirm(payload['session'],owner,payload['token'])
   value=self.session(payload['session'],owner);self.cancel_pending(value);return {'state':'conversation','session':payload['session'],'message':'Discarded the pending review. Nothing was saved.'}
  finally:self.owner.leave()

 async def native_read(self,text,members):
  from jarvis.calendar_context import current_calendar_access
  from jarvis.companion_memory import local_json
  if not current_calendar_access.get().read:raise ValueError('Household read access is required')
  from jarvis.household_speaker import current_speaker
  speaker=current_speaker.get().member_id
  if re.search(r'\b(?:my|me|mine|I)\b',text,re.I) and not members:
   if not speaker:raise ValueError('Whose preparation do you mean? Please name a household member.')
   members=[speaker]
  await self.refresh();projection=self.project()
  items=[v for v in projection['items'] if not members or v['person'] in members]
  schema={'type':'object','properties':{'selection':{'type':'array','items':{'type':'string','enum':['none']+[i['id'] for i in items]},'maxItems':6}},'required':['selection'],'additionalProperties':False}
  selected=await local_json(self.owner.provider,'Choose only supplied appointments relevant to this preparation-report/needs-attention question. Dates use Norway time. Return selection ids or [none]. No invented facts or actions.',{'today':self.owner.now().astimezone(ZONE).date().isoformat(),'latest':text,'appointments':[{k:i[k] for k in ('id','title','name','date','start','state')} for i in items]},schema,tokens=140)
  ids=selected.get('selection') if isinstance(selected,dict) else None
  if not isinstance(ids,list) or len(ids)>6 or any(v not in ['none']+[i['id'] for i in items] for v in ids):raise ValueError('I could not select that preparation report')
  chosen=[await self.resolve(i['id'],i['version']) for i in items if i['id'] in ids]
  lines=[]
  for item in chosen:
   details=(self.reports.get(item) or {}).get('details',{})
   lines.append(item['name']+' — '+item['title']+' ('+item['date']+'): '+('; '.join(self.summary(details)) if details else 'No dated preparation details have been reported.'))
   ready=[s['text'] for s in item['checklist'] if s['ready']]
   if ready:lines.append('Reported ready: '+', '.join(ready)+'. This is not confirmed attendance.')
   if item['gaps']:lines.append('Still needs checking: '+', '.join(item['gaps']).replace('_',' ')+'.')
  if not lines:lines=['I do not have a current matching preparation report in the next seven days.']
  if projection['source_failures']:lines.append('Some calendar sources could not be checked, so this may be incomplete.')
  lines.append('You can review or update these details under Household → Assistant → Needs attention.')
  return {'provider':'companion','status':'success','message':' '.join(lines),'cacheable':False,'planning_report_read':True}
