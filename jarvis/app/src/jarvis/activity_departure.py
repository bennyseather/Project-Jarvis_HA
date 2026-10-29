"""Read-only activity preparation plus a calculated home departure estimate."""
import asyncio,re,math
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from jarvis.calendar_context import current_calendar_access
from jarvis.companion_memory import local_json
from jarvis.companion_routing import CompanionRouting,reported_duration_quotes,reported_duration
from jarvis.companion_transport import coordinates
from jarvis.event_preparation import EventPreparation
from jarvis.calendar_insights import appointment_label
from jarvis.household_briefing import Brief
ZONE=ZoneInfo('Europe/Oslo')
async def departure(owner,text,key,source,state,members):
 def answer(message,status='success',**extra):return {'provider':'companion_routing','status':status,'message':message,'cacheable':False,'read_only':True,**extra}
 if not current_calendar_access.get().read:return answer('Household read access is needed.','forbidden')
 generation=owner.store.generation;revision=owner.profile._data['revision']
 named=any(re.search(r'\b'+re.escape(p['preferred_name'])+r'\b',text,re.I) for p in owner.profile._data['members'])
 query=re.sub(r'\bI\b','the household',text) if named else text
 try:resolved=await owner.agent.reads.resolve(query,'appointments',members,state,force=True)
 except ValueError as error:return answer(str(error),'clarification_required')
 if not resolved:return answer('Which activity and day should I check?','clarification_required')
 state['_resolved_read']=resolved
 obj=getattr(owner.container,'event_preparation',None)
 if obj is None:
  obj=EventPreparation(owner.profile,owner.container.home_assistant,getattr(owner.container,'proactive_allowed_entities',()),owner.provider,now=owner.now);owner.container.event_preparation=obj
 base=await obj.handle(text,key,resolved=resolved)
 if not base or base.get('status')!='success':return base or answer('Please name the activity and day.','clarification_required')
 plan=obj.sessions.get(str(key),{});focus=plan.get('source_focus',[])
 if not focus:return base
 thinking=getattr(owner.container,'household_thinking',None)
 if thinking is None:return base
 loaded=await asyncio.wait_for(thinking.reader.handle('activity departure',None,resolved=Brief(resolved['subjects'][0],resolved['start'],resolved['end']),structured_only=True,targets=tuple(resolved['subjects']),event_context=True),4)
 e=loaded['evidence']
 if e['source_failures'] or e['truncated']:return answer('I could not refresh enough calendar detail to calculate departure.','unavailable')
 events=[f for f in e['facts'] if f['kind']=='appointment' and not f['all_day'] and EventPreparation.event_identity(f) in focus]
 if not events:return answer('There is no timed appointment in that selection, so I cannot calculate a departure time.','clarification_required')
 event=min(events,key=lambda f:datetime.fromisoformat(f['start']).timestamp())
 phrases=reported_duration_quotes(text)
 schema={'type':'object','properties':{'include_preparation':{'type':'boolean'},'arrival_allowance_quote':{'type':'string','enum':['']+phrases}},'required':['include_preparation','arrival_allowance_quote'],'additionalProperties':False}
 frame=await local_json(owner.provider,'Does this question request preparation advice as well as when to leave? Set include_preparation accordingly. Select arrival_allowance_quote ONLY for an explicit request to arrive/park a stated duration early; never use activity duration or meal duration. Empty means use the labelled default planning allowance. JSON only.',{'question':text,'duration_phrases':phrases},schema,tokens=80)
 if not isinstance(frame,dict) or set(frame)!=set(schema['required']) or type(frame['include_preparation']) is not bool or frame['arrival_allowance_quote'] not in ['']+phrases:raise ValueError('Invalid departure interpretation')
 buffer=reported_duration(frame['arrival_allowance_quote']) if frame['arrival_allowance_quote'] else 10
 if buffer is None or buffer>180:return answer('Please give an arrival allowance up to three hours.','clarification_required')
 policy=owner.policy.data;approval=policy.get('interactive_home_routing',{})
 if policy.get('transport_preference')!='driving_first':return answer('Should I plan a drive from home, or another starting point and mode?','clarification_required')
 if not (approval.get('enabled') is True and approval.get('approval_source')):return answer('Home-to-Entur routing still needs the existing explicit sharing approval.','clarification_required')
 routing=getattr(owner.container,'companion_routing',None)
 if routing is None:routing=CompanionRouting(owner);owner.container.companion_routing=routing
 venue=routing.venue(event);minutes=None;basis=None
 at=datetime.fromisoformat(event['start']);arrive=at-timedelta(minutes=buffer)
 if venue and venue['planning_place_quote']:
  try:
   place=await asyncio.wait_for(asyncio.to_thread(routing.transport.place,venue['planning_place_quote']),6)
   home=coordinates(await asyncio.wait_for(owner.container.home_assistant.get_home_location(),4))
   if place:
    result=await asyncio.wait_for(asyncio.to_thread(routing.transport.route,home,coordinates(place['coordinates']),arrive,'driving'),12)
    options=result.get('options',[])
    n=options[0].get('duration_minutes') if result.get('state')=='available' and options else None
    if type(n) in (int,float) and math.isfinite(n) and 0<n<=1440:minutes=math.ceil(n);basis='Entur'
  except (ValueError,KeyError,TypeError,OSError,asyncio.TimeoutError):pass
 if minutes is None and venue and venue.get('usual_home_journey'):
  minutes=venue['usual_home_journey']['minutes'];basis='saved_user_estimate'
 if minutes is None:return answer((base['message']+' ' if frame['include_preparation'] else '')+'I need a usable activity venue or a confirmed usual home journey estimate before I can calculate when to leave.','clarification_required')
 if revision!=owner.profile._data['revision'] or generation!=owner.store.generation:return answer('The household information changed while I was checking. Please ask again.','unavailable')
 leave=(arrive-timedelta(minutes=minutes)).astimezone(ZONE);local_at=at.astimezone(ZONE)
 label=appointment_label(event);n=lambda value:str(int(value)) if int(value)==value else str(value)
 message=('For '+label+', starting at '+local_at.strftime('%H:%M')+' on '+local_at.strftime('%A %d %B')+', ')
 message=('If setting off from home, aim to leave around '+leave.strftime('%H:%M')+'. ') if frame['include_preparation'] else message+'if setting off from home, aim to leave around '+leave.strftime('%H:%M')+'. '
 message+=('That uses Entur’s '+n(minutes)+'-minute driving estimate' if basis=='Entur' else 'That uses your saved usual '+n(minutes)+'-minute journey estimate')+' plus a '+n(buffer)+'-minute '+('arrival allowance you requested.' if frame['arrival_allowance_quote'] else 'planning allowance for arriving early and parking.')
 if venue.get('usual_venue') and not frame['include_preparation']:message+=' The usual venue is planning context; check the current appointment location.'
 message+=' Allow for traffic and other delays.'
 if frame['include_preparation']:message=base['message']+' '+message
 return answer(message,composition='activity_preparation_departure',departure={'event_start':local_at.isoformat(),'leave_home_at':leave.isoformat(),'travel_minutes':minutes,'arrival_allowance_minutes':buffer,'basis':basis,'calendar_title':event['text'],'usual_venue_used':bool(venue.get('usual_venue')),'live_traffic':False},period={'start':resolved['start'],'end':resolved['end']})
