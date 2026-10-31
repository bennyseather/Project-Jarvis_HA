"""Ordinary Assist replies into the existing reviewed occurrence-report workflow.

Selected source identity is reference only; each proposal and confirmation reads
it again. No new storage or model-generated save authority.
"""
import re
from datetime import datetime,timedelta
from jarvis.calendar_context import current_calendar_access
from jarvis.companion_store import digest
from jarvis.planning_followup import SOURCE_NAMES
from jarvis.household_planner import get_planner,ZONE

def response(message,status='clarification_required',**extra):
 return {'provider':'companion','status':status,'message':message,'cacheable':False,**extra}
class PlanningConversation:
 def __init__(self,owner):self.owner=owner
 def identity(self,key,source):return 'assist-plan:'+digest(list(self.owner.agent.binding(key,source)))
 def clear(self,state):
  old=state.pop('planning_review',None)
  if old:
   session=self.owner.followups.sessions.get(old['session'])
   if session:self.owner.followups.cancel_pending(session)
 def pending(self,state):return bool(state.get('planning_review'))
 async def confirm(self,text,key,source,state):
  old=state.get('planning_review')
  if not old:return None
  value=' '.join(text.casefold().strip(' .!').split())
  if value in ('cancel','no','discard','never mind'):
   self.clear(state);return response('Discarded that preparation change.','success')
  if value not in ('yes','confirm','yes please','approve','confirm preparation change'):return None
  self.guard();owner=self.identity(key,source)
  try:result=await self.owner.followups.confirm(old['session'],owner,old['token'])
  except ValueError as e:
   self.clear(state);return response(str(e))
  state.pop('planning_review',None)
  item=result.get('item');message=result['message']
  if item:
   pending=[s['text'] for s in item['checklist'] if not s['ready']]
   ready=[s['text'] for s in item['checklist'] if s['ready']]
   if ready:message+=' Reported ready: '+', '.join(ready)+'.'
   if pending:message+=' Still to check: '+', '.join(pending)+'.'
   if not pending and item['checklist']:message+=' Everything on the current checklist is reported ready.'
   message+=' Ask when to leave for the updated departure plan.'
  # Preserve only this USER selection; all facts are re-read by its executor.
  if state.get('read_focus'):
   state['read_focus']['expires']=self.owner.clock()+600;state['read_focus'].pop('awaiting_detail',None)
  return response(message,'success',planning_report_saved=True,companion_agent_handled=True,agent_tool='planning_report')
 def guard(self):
  a=current_calendar_access.get()
  if not a.actor or not a.read or not a.write:raise ValueError('Your signed-in HA account needs permission to save preparation details.')
  get_planner(self.owner.container).guard(write=True)
 async def handle(self,text,key,source,state):
  self.guard();self.clear(state)
  focus=self.owner.agent.reads.prior(state)
  if not focus or len(focus.get('subjects',[]))!=1 or len(focus.get('event_focus',[]))!=1:
   return response('Which appointment is this for? Ask about the person and day first so I can keep the change with the right appointment.')
  person=focus['subjects'][0];identity=focus['event_focus'][0];f=self.owner.followups
  if person=='all':return response('Which person is this preparation detail for?')
  rows,_,failures,truncated=await f.load(focus['start'],focus['end'],person)
  if failures or truncated:return response('I could not check the complete appointment source. Please try again after the calendar refreshes.','unavailable')
  matches=[]
  for e in rows:
   actual=(e['title'],SOURCE_NAMES[e['source']],e['start'],e['end'],tuple(e['members']))
   if actual==tuple(identity):matches.append(f.build(e,person))
  if len(matches)!=1:return response('That appointment changed or is no longer available. Please ask about it again before saving a detail.')
  item=matches[0];f.items[item['id']]=item
  opened=await f.open(item['id'],item['version'],self.identity(key,source))
  try:result=await f.answer(opened['session'],self.identity(key,source),text,expected_detail=focus.get('awaiting_detail'))
  except ValueError as e:return response(str(e))
  if result['state']!='review':return response(result['message'])
  state['planning_review']={'session':result['session'],'token':result['token']}
  at=datetime.fromisoformat(item['start']).astimezone(ZONE).strftime('%A %d %B at %H:%M')
  return response('For '+item['name']+'’s '+item['title']+' on '+at+': '+ ' '.join(result['lines'])+' Shall I save that?',planning_report_review=True)
