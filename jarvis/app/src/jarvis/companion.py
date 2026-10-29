"""Opted-in local assistant: learning, preparation, coordination and reviewable ideas.

No bookings, notifications, reminder delivery, device actions or self-deployment.
The existing authenticated HA boundary and action confirmation remain authoritative.
"""
import asyncio,json,re,time
from collections import OrderedDict
from datetime import datetime,timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from jarvis.calendar_context import current_calendar_access
from jarvis.household_speaker import current_speaker,shared_knowledge_enabled
from jarvis.companion_store import CompanionStore,digest,bounded,secret,instruction_attempt
from jarvis.companion_memory import MemoryLearner,answer_memory,local_json,MemoryNoMatch
from jarvis.companion_dialogue import CompanionDialogue,response
from jarvis.companion_travel import TravelPreparer

POLICY_FIELDS={'schema_version','enabled','automatic_learning','automatic_travel','improvement_proposals','memory_retention','transport_preference','approval_source','recorded_on'}
class CompanionPolicy:
 def __init__(self,path,data):
  if not isinstance(data,dict) or set(data)-{'conversation_mode','interactive_home_routing'}!=POLICY_FIELDS or data['schema_version']!=1:raise ValueError('Invalid assistant policy')
  if any(type(data[k]) is not bool for k in ('enabled','automatic_learning','automatic_travel','improvement_proposals')):raise ValueError('Assistant policy flags must be explicit')
  if data['memory_retention']!='until_deleted' or data['transport_preference']!='driving_first':raise ValueError('Unsupported assistant preferences')
  if not data['approval_source'] or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',data['recorded_on']):raise ValueError('Assistant approval provenance required')
  if data.get('conversation_mode','legacy') not in ('legacy','qwen_tools'):raise ValueError('Invalid conversation mode')
  routing=data.get('interactive_home_routing')
  if routing is not None and (not isinstance(routing,dict) or set(routing)!={'enabled','approval_source','recorded_on'} or type(routing['enabled']) is not bool or not isinstance(routing['approval_source'],str) or not routing['approval_source'] or not isinstance(routing['recorded_on'],str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',routing['recorded_on'])):raise ValueError('Explicit home-routing approval provenance required')
  self.path=Path(path) if path else None;self.data=dict(data)
 @classmethod
 def load(cls,path):return cls(path,json.loads(Path(path).read_text(encoding='utf-8')))
 def update(self,**flags):
  if set(flags)-{'enabled','automatic_learning','automatic_travel'} or any(type(v) is not bool for v in flags.values()):raise ValueError('Invalid assistant policy change')
  self.data.update(flags)
  if self.path:
   temp=self.path.with_name(self.path.name+'.new');temp.write_text(json.dumps(self.data,indent=2)+'\n',encoding='utf-8');temp.chmod(0o600);temp.replace(self.path)

class BackgroundReasoning:
 def __init__(self,owner,provider):self.owner,self.provider=owner,provider
 def reason_local(self,**kwargs):
  if self.owner.foreground:return {'status':'unavailable','message':'Foreground conversation has priority'}
  return self.provider.reason_local(**kwargs)

class Companion:
 def __init__(self,container,policy,*,store=None,now=None,clock=time.monotonic):
  self.container,self.policy=container,policy;self.profile=container.household_profile
  self.now=now or (lambda:datetime.now(timezone.utc));self.clock=clock
  path=self.profile._source_path.with_name('jarvis.sqlite3') if getattr(self.profile,'_source_path',None) else None
  self.store=store or CompanionStore(path,now=self.now);self.provider=getattr(container,'local_reasoning_provider',None)
  self.foreground=0;self.last_activity=clock();self.last_scan=0.;self.pending=OrderedDict();self.selected=OrderedDict();self.intake_pending=OrderedDict();self.task=None
  self.background=BackgroundReasoning(self,self.provider)
  self.learner=MemoryLearner(self.profile,self.store,self.background)
  thinking=getattr(container,'household_thinking',None)
  self.dialogue=CompanionDialogue(self.profile,thinking,self.provider,now=self.now,clock=clock) if thinking is not None else None
  self.travel=TravelPreparer(container.home_assistant,container.travel_calendar_intelligence,self.store,self.background,
    research=getattr(container,'searxng_research',None),now=self.now) if getattr(container,'travel_calendar_intelligence',None) is not None else None
  from jarvis.companion_agent import QwenConversation
  self.agent=QwenConversation(self,clock=clock)
  from jarvis.household_agenda import HouseholdAgenda
  self.agenda=HouseholdAgenda(self)
  self.profile._companion=self
 async def process(self,operation,text,key,source):
  # Run at the authenticated bridge boundary after generic pending confirmations
  # have been handled, but before any legacy/household router can return early.
  if self.policy.data['enabled'] and self.policy.data.get('conversation_mode')=='qwen_tools':return await self.agent.process(operation,text,key,source)
  import inspect
  self.enter();used=False
  try:
   try:result=await self.handle(text,key,source)
   except Exception as error:
    logger=getattr(self.container,'logger',None)
    if logger:logger.warning('Assistant extension deferred: '+type(error).__name__)
    if re.search(r'^(?:forget|correct|pause|resume|stop)\b.*\b(?:learned|memory|learning|travel preparation)',text,re.I):
     return response('I could not safely complete that assistant setting or memory change. Nothing is confirmed.','unavailable')
    result=None
   if result is None:
    from jarvis.companion_context import observation_scope
    records=self.observations(text,self.subjects(text,key,source) or ())
    with observation_scope(records):
     used=True;result=await operation
   if isinstance(result,dict):
    try:self.after(text,result,key,source)
    except Exception as error:
     logger=getattr(self.container,'logger',None)
     if logger:logger.warning('Assistant observation deferred: '+type(error).__name__)
   return result
  finally:
   if not used and inspect.iscoroutine(operation):operation.close()
   self.leave()
 def binding(self,key,source):
  a=current_calendar_access.get();return (a.actor,str(key),source or '',current_speaker.get().member_id,self.profile._data['revision'])
 def enter(self):
  self.foreground+=1;self.last_activity=self.clock();self.agenda.interrupt()
 def leave(self):self.foreground=max(0,self.foreground-1);self.last_activity=self.clock()
 def start(self):
  if self.task is None:self.task=asyncio.create_task(self.run())
  self.agenda.start()
 async def close(self):
  await self.agenda.close()
  if self.task:
   self.task.cancel();await asyncio.gather(self.task,return_exceptions=True)
  self.store.close()
 async def run(self):
  while True:
   await asyncio.sleep(2)
   if not self.policy.data['enabled'] or self.foreground or self.clock()-self.last_activity<10:continue
   if self.policy.data['automatic_learning']:await self.learn_one()
   if self.travel and self.policy.data['automatic_travel'] and not self.foreground and self.clock()-self.last_activity>=10 and self.clock()-self.last_scan>=900:
    self.last_scan=self.clock()
    try:await self.travel.scan(maximum=2)
    except asyncio.CancelledError:raise
    except Exception:self.travel.status='preparation_needs_retry'
 async def learn_one(self,*,foreground=False,job_id=None):
  job=self.store.next_job(job_id)
  if job is None:return False
  learner=MemoryLearner(self.profile,self.store,self.provider) if foreground else self.learner
  try:
   records=await learner.extract(job)
   if not self.policy.data['improvement_proposals']:records=[r for r in records if r['kind']!='improvement']
   expected=job['source'].get('preference_subjects')
   if expected is not None and (len(records)!=1 or records[0]['kind']!='preference' or records[0]['subjects']!=sorted(expected)):raise ValueError('Preference subject/type needs another check')
   if job['source'].get('correct_memory') and len(records)!=1:raise ValueError('A correction needs one clear replacement')
   ids=self.store.finish(job,records);return {'saved':bool(ids),'ids':ids}
  except asyncio.CancelledError:raise
  except Exception:self.store.retry(job);return {'saved':False,'ids':[]}
 def capture(self,text,result,key,source):
  access=current_calendar_access.get()
  if not (self.policy.data['enabled'] and self.policy.data['automatic_learning'] and access.actor and access.write and shared_knowledge_enabled(self.profile._data)):return
  value=' '.join(text.strip().split());low=value.casefold()
  if not 8<=len(value)<=1200 or secret(value) or instruction_attempt(value):return
  if re.match(r'^(?:yes|no|confirm|approve|cancel|stop|forget|delete|correct|remember|save|add|create|book|move|reschedule|set|turn|switch|unlock|open)\b',low):return
  names=[p['preferred_name'] for p in self.profile._data['members']]
  declarative=bool(re.search(r"\b(?:i|we|jeg|eg) (?:prefer|like|dislike|hate|usually|often|always|need|want|plan|will|am|have|foretrekker|liker|vil|skal|har|er)\b|\bi['’]m\b",value,re.I)
                   or any(re.search(r'\b'+re.escape(n)+r"(?:['’]s)?\s+(?:is|has|will|likes?|prefers?|needs?|usually|often|starts?|er|har|skal|liker|foretrekker)\b",value,re.I) for n in names))
  development=bool(self.policy.data['improvement_proposals'] and re.search(r'\b(jarvis|you|your)\b.{0,70}\b(improve|misunderstand|wrong|bug|slow|should|clips)\b',value,re.I))
  if not declarative and not development:return
  # A question alone supplies no new fact. A clearly embedded reported
  # preference can still be selected by Qwen from the user statement.
  previous=self.dialogue.previous(key,source) if self.dialogue else None
  context={'conversation':digest([str(key)]),'actor':digest([access.actor]),'speaker':current_speaker.get().member_id,'speaker_basis':current_speaker.get().basis,
    'anchor':self.now().astimezone(ZoneInfo('Europe/Oslo')).date().isoformat(),
    'prior_subjects':previous['subjects'] if previous else [],
    'explicit_correction':bool(re.search(r'\b(?:actually|instead|no longer|from now|egentlig|heller|ikke lenger)\b',value,re.I))}
  try:self.store.enqueue(value,context)
  except ValueError:pass
 def statement_candidate(self,text):
  # A cheap domain/shape gate, NOT a preference verb grammar. Qwen decides
  # whether the statement actually supplies a preference worth retaining.
  value=' '.join(text.strip().split())
  if not 8<=len(value)<=600 or '?' in value or secret(value) or instruction_attempt(value):return False
  if re.match(r'^(?:what|when|where|why|how|does|do|did|is|are|can|could|would|will|show|tell|yes|no|confirm|approve|cancel|stop|forget|delete|correct|remember|save|add|create|book|move|reschedule|set|turn|switch|unlock|open)\b',value,re.I):return False
  first=bool(re.search(r"\b(?:i|my|mine|jeg|eg|min|mitt)\b|\bi['\u2019]m\b",value,re.I))
  named=any(re.search(r'\b'+re.escape(p['preferred_name'])+r'\b',value,re.I) for p in self.profile._data['members'])
  return first or named
 async def preference_intake(self,text,key,source,*,intent='preference'):
  value=' '.join(text.strip().split());access=current_calendar_access.get();binding=self.binding(key,source);generation=self.store.generation
  prior=self.intake_pending.pop(str(key),None);clarified=False;clarification_quote='';records=None
  if prior and prior['binding']==binding and prior['expires']>self.clock() and prior['generation']==generation:
   members=[p for p in self.profile._data['members'] if re.fullmatch(r"(?:(?:it(?:'s| is)|that(?:'s| is)|for) )?"+re.escape(p['preferred_name'])+r"(?:'s)?[.!]?",value,re.I)]
   if len(members)==1:
    subjects=[members[0]['id']];clarification_quote=value;value=prior['text'];clarified=True
    records=[{**r,'subjects':subjects} for r in prior['records']];context={**prior['context']}
  if not clarified:
   if intent!='remember' and not self.statement_candidate(value):return None
   if not (self.policy.data['enabled'] and self.policy.data['automatic_learning'] and access.write):return None
   context={'conversation':digest([str(key)]),'actor':digest([access.actor]),'speaker':current_speaker.get().member_id,'speaker_basis':current_speaker.get().basis,
    'anchor':self.now().astimezone(ZoneInfo('Europe/Oslo')).date().isoformat(),'prior_subjects':[],
    'intake_preference_check':intent=='preference','explicit_correction':False,'text':value}
   try:records=await MemoryLearner(self.profile,self.store,self.provider).extract({'source':context})
   except (ValueError,asyncio.TimeoutError):return None
   if len(records)!=1 or records[0]['kind'] not in (('preference',) if intent=='preference' else ('preference','fact','plan','hint')):return None
   subjects=records[0]['subjects']
  noun='preference' if records[0]['kind']=='preference' else 'detail'
  def answer(message,status='success',**extra):return {**response(message,status),'companion_intake':True,**extra}
  if generation!=self.store.generation or binding!=self.binding(key,source):return answer('That learning request changed while I was checking it. Please tell me again.','unavailable')
  self.revoke_other_reviews(key)
  if not self.policy.data['enabled'] or not self.policy.data['automatic_learning']:
   return answer('Automatic learning is paused, so I have not saved that preference.','unavailable')
  if not access.write:return answer('Your signed-in HA account needs permission to save that preference.','forbidden')
  if not subjects:
   self.intake_pending[str(key)]={'text':value,'records':records,'context':context,'binding':binding,'generation':generation,'expires':self.clock()+300}
   while len(self.intake_pending)>100:self.intake_pending.popitem(last=False)
   return answer('Whose '+noun+' is that? Please name the household member.','clarification_required')
  if records[0]['kind']=='preference':context['preference_subjects']=sorted(subjects)
  if clarified:
   context.update(clarified_subjects=subjects,clarification_quote=clarification_quote)
   # Repair the exact unowned statement from an earlier version. A name reply
   # supplies this statement's owner only; it never authenticates the speaker.
   unowned=[m for m in self.store.memories(include_historical=True) if m['quote']==value and not m['subjects'] and m['kind']=='preference']
   if len(unowned)==1:context.update(correct_memory=unowned[0]['id'],explicit_correction=True)
  context.pop('text',None)
  job_id=self.store.enqueue(value,context);ids=[]
  if job_id:
   job=self.store.next_job(job_id)
   try:ids=self.store.finish(job,records) if job else []
   except ValueError:
    if job:self.store.retry(job)
  else:ids=[m['id'] for m in self.store.memories() if m['quote']==value and m['subjects']==sorted(subjects) and m['kind']=='preference']
  if not ids:return answer('I could not finish saving that preference yet. It needs another learning check; I have not confirmed it as saved.','unavailable')
  self.selected[str(key)]={'binding':binding,'ids':ids,'expires':self.clock()+300}
  names=' and '.join(next(p['preferred_name'] for p in self.profile._data['members'] if p['id']==member) for member in subjects)
  return answer('Got it. I have saved that '+noun+' for '+names+'.',memory_saved=True,memory_ids=ids)
 def hint(self,key,result):
  period=result.get('period')
  if period:return period
  calendar=getattr(self.container,'calendar_conversation',None)
  selected=getattr(getattr(calendar,'editing',None),'sessions',{}).get(str(key),{}).get('selection')
  if selected:return {'start':selected['start'],'end':selected['end']}
  prep=getattr(self.container,'event_preparation',None);state=getattr(prep,'sessions',{}).get(str(key),{})
  if state.get('start') and state.get('end'):return {'start':state['start'],'end':state['end']}
  return None
 def after(self,text,result,key,source):
  if not result.get('companion_intake') and not result.get('companion_agent_handled'):self.capture(text,result,key,source)
  if self.dialogue and not result.get('companion_coordination'):self.dialogue.observe(text,result,key,source,self.hint(key,result))
 def revoke_other_reviews(self,key):
  calendar=getattr(self.container,'calendar_conversation',None)
  if calendar is not None:
   calendar.clear(key)
   editing=getattr(calendar,'editing',None)
   if editing is not None:editing.clear(key)
  edits=getattr(self.profile,'_edits',None)
  if edits is not None:edits.observe_turn('assistant conversation',key)
 def subjects(self,text,key,source):
  named=[p['id'] for p in self.profile._data['members'] if re.search(r'\b'+re.escape(p['preferred_name'])+r'\b',text,re.I)]
  if named:return named
  if re.search(r'\b(my|me|i|jeg|meg|min|mitt)\b',text,re.I):
   speaker=current_speaker.get().member_id
   return [speaker] if speaker else None
  old=self.dialogue.previous(key,source) if self.dialogue else None
  return old['subjects'] if old else []
 async def handle(self,text,key,source=None,*,semantic=None):
  access=current_calendar_access.get()
  if not access.actor or not access.read or not shared_knowledge_enabled(self.profile._data):return None
  value=' '.join(text.casefold().replace('’',"'").strip(' .?!').split());binding=self.binding(key,source)
  previous=self.dialogue.previous(key,source) if self.dialogue else None
  if previous and len(previous['subjects'])>1 and re.search(r'\b(?:her|his|their) (?:birthday|age|job)\b',value):
   return response('Whose information do you mean? Please use their name.')
  if value!='forget that':self.selected.pop(str(key),None)
  intake=await self.preference_intake(text,key,source) if semantic is None else None
  if intake is not None:
   self.pending.pop(str(key),None);return intake
  old=self.pending.pop(str(key),None)
  if old and old['binding']==binding and old['expires']>self.clock() and value in ('yes','confirm','approve','yes please'):
   if not access.write:return response('Your signed-in HA account needs permission to change learned memories.','forbidden')
   self.revoke_other_reviews(key);count=self.store.forget();self.selected.clear();return response('Cleared '+str(count)+' learned memories and pending learning. Your household profile and calendar are unchanged.','success')
  if value in ('pause automatic learning','stop automatic learning','resume automatic learning','pause travel preparation','stop travel preparation','resume travel preparation'):
   if not access.write:return response('Your signed-in HA account needs control permission for that setting.','forbidden')
   learning='learning' in value;enabled=value.startswith('resume')
   self.policy.update(**{'automatic_learning' if learning else 'automatic_travel':enabled});self.revoke_other_reviews(key)
   return response(('Automatic learning' if learning else 'Automatic travel preparation')+(' resumed.' if enabled else ' paused. Existing records are retained.'),'success')
  if value=='forget all learned memories':
   if not access.write:return response('Your signed-in HA account needs memory control permission.','forbidden')
   self.revoke_other_reviews(key);self.pending[str(key)]={'binding':binding,'expires':self.clock()+300}
   while len(self.pending)>100:self.pending.popitem(last=False)
   return response('This will clear learned conversation memories and pending learning, while keeping your household profile and calendar. Shall I clear them?')
  if value=='forget that':
   selected=self.selected.get(str(key))
   if selected and selected['binding']==binding and selected['expires']>self.clock():
    if len(selected['ids'])!=1:return response('Which learned memory should I forget? Please use its memory ID.')
    value='forget learned memory '+selected['ids'][0].casefold()
  forget=re.fullmatch(r'forget (?:learned )?memory (m[0-9a-f]{8})',value)
  if forget:
   if not access.write:return response('Your signed-in HA account needs memory control permission.','forbidden')
   known=next((m for m in self.store.memories(include_historical=True) if m['id'].casefold()==forget[1]),None)
   if known is None:return response('I could not find that learned memory.')
   self.revoke_other_reviews(key);self.store.forget([known['id']]);return response('Forgot that learned memory.','success')
  correction=re.fullmatch(r'correct (?:learned )?memory (M[0-9a-fA-F]{8})\s*(?:to|:)\s*(.+)',text.strip(),re.I)
  if correction:
   if not access.write:return response('Your signed-in HA account needs memory control permission.','forbidden')
   known=next((m for m in self.store.memories(include_historical=True) if m['id'].casefold()==correction[1].casefold()),None)
   if known is None:return response('I could not find that learned memory.')
   replacement=bounded(correction[2],1000)
   self.revoke_other_reviews(key);job_id=self.store.enqueue(replacement,{'conversation':digest([str(key)]),'actor':digest([access.actor]),'speaker':current_speaker.get().member_id,'speaker_basis':current_speaker.get().basis,
     'anchor':self.now().astimezone(ZoneInfo('Europe/Oslo')).date().isoformat(),'correct_memory':known['id'],'explicit_correction':True,'prior_subjects':known['subjects']})
   applied=await self.learn_one(foreground=True,job_id=job_id) if job_id else None
   if not applied or not applied['saved']:return response('I could not apply that correction yet. The previous memory is retained while the queued correction needs another check.','unavailable')
   return response('Corrected that learned memory. You can review it on the Assistant page.','success')
  memory_list=semantic=='memory_list' or value in ('show learned memories','show conversation memories','what have you learned','what have you picked up','what did you pick up from our conversations')
  memory_question=semantic=='memory' or bool(re.search(r'\b(?:remember(?:ed)?|told|mention(?:ed)?|prefer(?:s|ence|ences)?|favourite|favorite|dislike|learn(?:ed)?)\b',value)) and bool(re.match(r'^(?:what|when|which|how|do|does|did|can|could|show|tell)\b',value))
  if memory_list or memory_question:
   subjects=self.subjects(text,key,source)
   if memory_list and not re.search(r'\b(my|me|i)\b',value) and not any(re.search(r'\b'+re.escape(p['preferred_name'])+r'\b',text,re.I) for p in self.profile._data['members']):subjects=[]
   if subjects is None:return response('Whose information do you mean? Please name a household member, or ask when your voice is matched.')
   # Drain at most one queued statement when explicitly asking about memory.
   # Other questions never wait for background learning.
   if self.policy.data['automatic_learning'] and self.store.job_counts().get('queued'):await self.learn_one(foreground=True)
   rows=self.store.memories(include_historical=True) if memory_list else self.store.relevant(text,subjects)
   if memory_list and subjects:rows=[r for r in rows if not r['subjects'] or set(r['subjects']).intersection(subjects)]
   if not rows:
    if memory_list:return response('I have not learned any matching conversation details yet. Useful statements are checked in the background; your confirmed household information stays available.','success')
    return None
   self.revoke_other_reviews(key)
   ids=[r['id'] for r in rows[:6]]
   if memory_list:
    text_out='Here are the details I have kept from conversations: '+'; '.join(r['id']+': “'+r['quote']+'”'+(' (possible inference)' if r['kind']=='hint' else ' (historical)' if not r['currently_applicable'] else '') for r in rows[:6])+'. You can correct or forget one by its memory ID.'
   else:
    try:text_out,ids=await answer_memory(self.provider,text,rows,{p['id']:p['preferred_name'] for p in self.profile._data['members']},current_speaker.get().member_id)
    except MemoryNoMatch:return None
    except (ValueError,asyncio.TimeoutError):
     r=rows[0];ids=[r['id']];text_out='In an earlier conversation, '+('an unidentified speaker' if not r['subjects'] else ' and '.join(next(p['preferred_name'] for p in self.profile._data['members'] if p['id']==s) for s in r['subjects']))+' said: “'+r['quote']+'”.'+(' Any further interpretation is uncertain.' if r['kind']=='hint' else '')
   self.selected[str(key)]={'binding':binding,'ids':ids,'expires':self.clock()+300}
   while len(self.selected)>100:self.selected.popitem(last=False)
   return response(text_out,'success')
  trip_input=re.fullmatch(r'update travel brief (T[0-9a-f]{10})\s*:\s*(.+)',text.strip(),re.I)
  if trip_input and self.travel:
   if not access.write:return response('Your signed-in HA account needs control permission to save trip details.','forbidden')
   try:await self.travel.update_input(trip_input[1],trip_input[2],self.provider)
   except (ValueError,asyncio.TimeoutError) as error:return response(str(error))
   self.last_scan=0;self.revoke_other_reviews(key)
   return response('Saved those details for this itinerary. I will refresh the airport brief in the background; no bookings or calendar entries were changed.','success')
  travel_read=semantic=='travel_brief' or bool(re.search(r'\b(?:travel briefs?|airport plans?|airport preparation|prepared for (?:my|the|benny)|what have you prepared)\b',value))
  if travel_read and self.travel:
   named={p['id'] for p in self.profile._data['members'] if re.search(r'\b'+re.escape(p['preferred_name'])+r'\b',text,re.I)}
   if named and 'benny' not in named:return response('I do not have a connected travel calendar for that person. Benny’s prepared travel briefs are shared with the household.','unavailable')
   if re.search(r'\b(my|me|mine)\b',value):
    speaker=current_speaker.get().member_id
    if speaker is None:return response('Whose travel preparation do you mean? Please name the traveller.')
    if speaker!='benny':return response('I do not have a connected travel calendar for that person. Benny’s prepared travel briefs are shared with the household.','unavailable')
   rows=self.store.briefs()
   if rows:
    self.revoke_other_reviews(key);summary=('Benny’s travel brief: ' if current_speaker.get().member_id!='benny' else '')+' '.join(r.get('summary','') for r in rows[:2])
    if self.travel.status not in ('checked','not_checked'):summary+=' I could not refresh the travel calendar at the last check; verify the current booking before relying on this preparation.'
    return response(summary,'success')
   if 'what needs my attention' not in value:return response('I have not prepared an upcoming flight brief yet. I check the connected travel calendar automatically; an unknown starting point or missing source will appear as a question.','success')
  if semantic=='development' or re.search(r'\b(?:development proposals|improvement proposals|improve yourself|improve your own|your development|your own code|what should you improve)\b',value):
   self.revoke_other_reviews(key);rows=self.store.improvements()
   if rows:return response('I have these improvement ideas for review: '+'; '.join(r.get('proposal') or r.get('quote','') for r in rows[:4])+'. These are proposals; I have not changed or executed my own code.','success')
   return response('I can collect and draft improvement proposals using local Qwen. The next development stage is an isolated code-and-test workspace; I cannot yet change or deploy my running code myself.','success')
  if self.policy.data['enabled'] and self.dialogue:
   result=await self.dialogue.handle(text,key,source)
   if result is not None:self.revoke_other_reviews(key);return result
  return None
 def observations(self,text,subjects=()):
  return [{k:r[k] for k in ('id','kind','subjects','quote','interpretation','confidence','anchor','valid_from','valid_until','date_unresolved','currently_applicable')} for r in self.store.relevant(text,subjects,maximum=5)]
 def overview(self):
  return {'conversation_mode':self.policy.data.get('conversation_mode','legacy'),'enabled':self.policy.data['enabled'],'learning_enabled':self.policy.data['automatic_learning'],'travel_enabled':self.policy.data['automatic_travel'],
   'retention':'Until corrected or deleted','transport_preference':'Driving first, public transport alternatives',
   'people':{p['id']:p['preferred_name'] for p in self.profile._data['members']},'memories':self.store.memories(include_historical=True)[:30],'learning_jobs':self.store.job_counts(),'travel_briefs':self.store.briefs()[:8],
   'household_planning':self.agenda.project(),'travel_status':self.travel.status if self.travel else 'not_configured','improvements':self.store.improvements()[:10],
   'development_mode':'Ideas and proposals only; no autonomous code execution or deployment','read_only':True}

def create_companion(container):
 profile=getattr(container,'household_profile',None);source=getattr(profile,'_source_path',None)
 if source is None or not shared_knowledge_enabled(profile._data):return None
 policy_path=source.with_name('assistant_policy.json')
 if not policy_path.exists():return None
 return Companion(container,CompanionPolicy.load(policy_path))
