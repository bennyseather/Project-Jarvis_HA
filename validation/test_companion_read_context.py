"""Cross-capability user intent, fresh reads and scoped memory regressions."""
import json,unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock
from jarvis.companion import Companion,CompanionPolicy
from jarvis.companion_store import CompanionStore
from jarvis.companion_context import current_observations
from jarvis.calendar_context import calendar_scope
from jarvis.household_speaker import speaker_scope
from jarvis.companion_read_context import ReadDialogue,duration_quotes
from jarvis.calendar_insights import duration_minutes
from test_planning_preparation_bundle import profile
from test_companion_coordinator import POLICY,NOW
from test_companion_agent import Provider as AgentProvider,plan
from test_companion_memory import store_record

def frame(subjects=None,**kw):
 return dict(intent='read',subjects=subjects or ['mia'],date_quote='',purpose='overview',window='all_day',between=False,duration_quote='',**kw) if not kw else {**frame(subjects),**kw}
class Provider(AgentProvider):
 def __init__(self):super().__init__();self.frames=[]
 def reason_local(self,**kw):
  if 'date_quote' in kw['response_schema']['properties']:
   self.calls.append(kw);return {'status':'success','message':json.dumps(self.frames.pop(0))}
  return super().reason_local(**kw)
class ReadTests(unittest.IsolatedAsyncioTestCase):
 def setUp(self):
  self.p=profile();self.provider=Provider();self.store=CompanionStore(now=lambda:NOW);self.addCleanup(self.store.close);self.clock=[1]
  self.thinking=SimpleNamespace(sessions={},handle=AsyncMock())
  self.c=SimpleNamespace(household_profile=self.p,home_assistant=object(),travel_calendar_intelligence=None,local_reasoning_provider=self.provider,household_thinking=self.thinking)
  self.a=Companion(self.c,CompanionPolicy(None,{**deepcopy(POLICY),'conversation_mode':'qwen_tools'}),store=self.store,now=lambda:NOW,clock=lambda:self.clock[0])
 def scopes(self,member=None):return speaker_scope({'member_id':member,'basis':'voice_match' if member else 'unknown','conversation_id':'s'},self.p,'s')
 def prior(self,**kw):
  self.state=self.a.agent.state('s','phone')
  self.state['read_focus']={**dict(subjects=['mia'],start='2026-10-29',end='2026-10-30',question='What does Mia have tomorrow?',task='What does Mia have tomorrow?',purpose='overview',window='all_day',between=False,duration_minutes=None,expires=600),**kw}
 async def resolve(self,text,decision,tool='plans',speaker=None):
  self.provider.frames.append(decision)
  with calendar_scope({'actor':'u','read':True,'write':True}),self.scopes(speaker):
   if not hasattr(self,'state'):self.prior()
   return await self.a.agent.reads.resolve(text,tool,decision['subjects'],self.state)
 async def test_preparation_after_overview_keeps_person_and_date(self):
  r=await self.resolve('What should she bring?',frame(purpose='preparation'),tool='appointments')
  self.assertEqual((r['subjects'],r['start']),(('mia',),'2026-10-29'));self.assertEqual(r['previous_question'],'What does Mia have tomorrow?')
 async def test_date_only_followup_is_computed_from_prior_period(self):
  r=await self.resolve('And Friday?',frame(date_quote='friday'));self.assertEqual(r['start'],'2026-10-30')
 async def test_correction_replaces_child_not_confirmed_profile(self):
  before=deepcopy(self.p._data);r=await self.resolve('Actually I meant Emrik',frame(['emrik'],intent='correction'))
  self.assertEqual(r['subjects'],('emrik',));self.assertEqual(before,self.p._data)
 async def test_driver_joins_child_and_is_not_assigned(self):
  r=await self.resolve('Could Linda take her instead?',frame(['linda'],purpose='conflicts'))
  self.assertEqual(set(r['subjects']),{'mia','linda'});self.assertTrue(r['companion_coordination'])
 async def test_new_named_question_replaces_old_person(self):
  r=await self.resolve('What does Linda have Friday?',frame(['linda'],date_quote='friday'));self.assertEqual(r['subjects'],('linda',))
 async def test_unknown_first_person_cannot_be_guessed_from_child(self):
  with self.assertRaisesRegex(ValueError,'Whose'):await self.resolve('Could I take Mia instead?',frame(['benny','mia']))
 async def test_multiple_possible_pronouns_require_clarification(self):
  with calendar_scope({'actor':'u','read':True,'write':True}):self.prior(subjects=['mia','linda'])
  with self.assertRaisesRegex(ValueError,'Which household'):await self.resolve('What should she bring?',frame(['mia'],purpose='preparation'),tool='appointments')
 async def test_model_cannot_add_unmentioned_owner(self):
  with self.assertRaisesRegex(ValueError,'Which household'):await self.resolve('And Friday?',frame(['benny'],date_quote='friday'))
 async def test_model_cannot_ignore_explicit_latest_date(self):
  with self.assertRaisesRegex(ValueError,'Which date'):await self.resolve('And Friday?',frame())
 async def test_model_cannot_invent_date_or_duration(self):
  for kw in ({'date_quote':'2026-11-01'},{'duration_quote':'45 minutes'}):
   with self.assertRaisesRegex(ValueError,'date or duration'):await self.resolve('And Friday?',frame(**kw))
 async def test_between_is_supported_by_latest_or_prior_user_question(self):
  with calendar_scope({'actor':'u','read':True,'write':True}):self.prior(purpose='availability')
  with self.assertRaisesRegex(ValueError,'Which appointments'):await self.resolve('And Friday?',frame(date_quote='friday',purpose='availability',between=True))
 async def test_duration_answer_preserves_between_task(self):
  with calendar_scope({'actor':'u','read':True,'write':True}):self.prior(purpose='availability',between=True,task='Can we fit dinner between those appointments?')
  r=await self.resolve('About 45 minutes',frame(purpose='availability',between=True,duration_quote='45 minutes'))
  self.assertEqual(r['requested_duration'],45);self.assertTrue(r['between']);self.assertEqual(r['start'],'2026-10-29')
 async def test_date_change_carries_requested_duration_but_new_goal_drops_it(self):
  with calendar_scope({'actor':'u','read':True,'write':True}):self.prior(purpose='availability',between=True,duration_minutes=45)
  r=await self.resolve('And Friday?',frame(date_quote='friday',purpose='availability',between=True));self.assertEqual(r['requested_duration'],45)
  r=await self.resolve('What does Mia have Friday?',frame(date_quote='friday'));self.assertIsNone(r['requested_duration'])
 async def test_expiry_discards_prior_user_task(self):
  with calendar_scope({'actor':'u','read':True,'write':True}):self.prior()
  self.clock[0]=700;self.assertIsNone(self.a.agent.reads.prior(self.state));self.assertNotIn('read_focus',self.state)
 async def test_context_resets_on_actor_source_profile_and_voice_change(self):
  for context in ({'actor':'other','read':True,'write':True},{'actor':'u','read':True,'write':True}):
   with calendar_scope(context):
    self.prior();self.assertNotIn('read_focus',self.a.agent.state('s','other'))
  with calendar_scope({'actor':'u','read':True,'write':True}),self.scopes('benny'):self.prior()
  with calendar_scope({'actor':'u','read':True,'write':True}),self.scopes('linda'):self.assertNotIn('read_focus',self.a.agent.state('s','phone'))
  with calendar_scope({'actor':'u','read':True,'write':True}):self.prior();self.p._data['revision']+=1;self.assertNotIn('read_focus',self.a.agent.state('s','phone'))
 async def test_action_and_secret_text_do_not_use_shared_read_bypass(self):
  with calendar_scope({'actor':'u','read':True,'write':True}):
   self.prior()
   for text in ('What does Mia have and unlock the door?','My password is example123'):
    self.assertIsNone(await self.a.agent.reads.resolve(text,'plans',['mia'],self.state))
  self.assertEqual(self.provider.calls,[])
 async def test_fresh_direct_question_keeps_fast_existing_path(self):
  with calendar_scope({'actor':'u','read':True,'write':True}):
   state=self.a.agent.state('new','phone');self.assertIsNone(await self.a.agent.reads.resolve('What does Mia have tomorrow?','plans',['mia'],state))
  self.assertEqual(self.provider.calls,[])
 async def test_non_read_topic_clears_shared_task(self):
  with calendar_scope({'actor':'u','read':True,'write':True}):self.prior()
  self.a.agent.reads.observe('Hi','general',{'status':'success'},[],self.state);self.assertNotIn('read_focus',self.state)
 async def test_qwen_path_injects_saved_user_observations_then_resets_them(self):
  store_record(self.store,'Benny prefers driving to the airport.')
  captured=[]
  async def handle(text,key,**kw):
   captured.extend(current_observations.get());return {'status':'success','provider':'household_thinking','message':'A fictional sourced answer.'}
  self.thinking.handle=handle;self.provider.plans=[plan('plans',members=['benny'])]
  async def original():raise AssertionError('Unexpected legacy router')
  with calendar_scope({'actor':'u','read':True,'write':True}):await self.a.process(original(),'What should Benny consider for airport transport tomorrow?','s','phone')
  self.assertEqual(captured[0]['subjects'],['benny']);self.assertEqual(current_observations.get(),())
 async def test_known_voice_switch_clears_history_not_saved_memories(self):
  mid=store_record(self.store,'Benny prefers driving.')
  with calendar_scope({'actor':'u','read':True,'write':True}),self.scopes('benny'):
   self.prior();self.state['history']=[{'role':'user','text':'Benny task'}]
  with calendar_scope({'actor':'u','read':True,'write':True}),self.scopes('linda'):
   state=self.a.agent.state('s','phone');self.assertEqual(state['history'],[]);self.assertNotIn('read_focus',state)
  self.assertEqual(self.store.memories()[0]['id'],mid)
 async def test_forget_during_qwen_household_read_withdraws_old_observations(self):
  mid=store_record(self.store,'Benny prefers driving to the airport.')
  async def handle(text,key,**kw):
   self.assertTrue(current_observations.get());self.store.forget([mid]);return {'status':'success','provider':'household_thinking','message':'The old remembered detail.'}
  self.thinking.handle=handle;self.provider.plans=[plan('plans',members=['benny'])]
  async def original():raise AssertionError('Unexpected legacy router')
  with calendar_scope({'actor':'u','read':True,'write':True}):r=await self.a.process(original(),'What should Benny consider for airport transport tomorrow?','s','phone')
  self.assertEqual(r['status'],'unavailable');self.assertNotIn('old remembered',r['message']);self.assertEqual(self.store.memories(),[])
 async def test_whole_household_date_followup_keeps_collective_scope(self):
  with calendar_scope({'actor':'u','read':True,'write':True}):self.prior(subjects=['all'])
  r=await self.resolve('And Friday?',frame(['all'],date_quote='friday'));self.assertEqual(r['subjects'],('all',));self.assertEqual(r['start'],'2026-10-30')
 async def test_unresolved_clarification_does_not_relabel_old_calendar_as_latest_task(self):
  with calendar_scope({'actor':'u','read':True,'write':True}):self.prior()
  old=deepcopy(self.state['read_focus']);self.thinking.sessions['s']={'subjects':('mia',),'start':'2026-10-29','end':'2026-10-30','question':'What does Mia have tomorrow?'}
  self.a.agent.reads.observe('Could I take her?', 'plans', {'status':'clarification_required'},[],self.state)
  self.assertEqual(self.state['read_focus'],old)
 def test_generic_schedule_question_is_not_a_literal_activity(self):
  from jarvis.event_activity import requirement,requested
  for q in ('What does Mia have tomorrow?','What has she got on Friday?','What is she doing?'):
   self.assertFalse(requested(requirement(q,['Mia'])),q)
 async def test_general_qwen_answer_receives_relevant_saved_user_reports(self):
  store_record(self.store,'Benny prefers high fidelity music.',topic='music',tags=['music','fidelity'])
  self.provider.plans=[plan('general','answer',members=['benny'],answer='Benny values high fidelity, so sound quality would be worth prioritising.')]
  async def original():raise AssertionError('Unexpected legacy router')
  with calendar_scope({'actor':'u','read':True,'write':True}):r=await self.a.process(original(),'What matters to Benny when choosing music equipment?','s','phone')
  synthesis=json.loads(self.provider.calls[-1]['input_messages'][0]['content'])
  self.assertEqual(synthesis['reported_user_context'][0]['subjects'],['benny']);self.assertIn('high fidelity',r['message'])
 def test_helper_comparison_distinguishes_early_event_from_later_option(self):
  from jarvis.calendar_insights import helper_timing
  evidence={'people':{'mia':'Mia','linda':'Linda'},'facts':[
   {'id':'R1','kind':'routine','owners':['linda'],'text':'Usual work: Leave for work around 08:00; finish around 16:00.','dates':['2026-10-29']},
   {'id':'E1','kind':'appointment','owners':['mia'],'text':'Band rehearsal','date':'2026-10-29','all_day':False,'local_start':'15:40'},
   {'id':'E2','kind':'appointment','owners':['mia'],'text':'Gymnastics','date':'2026-10-29','all_day':False,'local_start':'17:00'}]}
  rows=helper_timing(evidence);self.assertEqual([r['minutes_after_usual_work_finish'] for r in rows],[-20,60])
  self.assertTrue(all('not actual work attendance' in r['basis'] for r in rows))
  evidence['facts'][0]['dates']=['2026-10-30'];self.assertEqual(helper_timing(evidence),[])
 def test_coordination_cannot_reassign_child_event_or_invent_late_impossibility(self):
  from jarvis.household_thinking import HouseholdThinking
  row={'helper':'Linda','owner':'Mia','event':'Band rehearsal','start':'15:40','usual_work_finish':'16:00','minutes_after_usual_work_finish':-20}
  board={'purpose':'conflicts','duration_clarification_needed':False,'helper_timing_relationships':[row,{**row,'event':'Gymnastics','start':'17:00','minutes_after_usual_work_finish':60}],
    'different_person_parallel_commitments':[],'potential_same_person_conflicts':[],'no_same_person_timed_overlap_found':True,'timetable_relationships':[]}
  for text in ("Linda's Band rehearsal starts before her usual finish.", 'The rehearsal starts before work ends, but Linda cannot take Mia to Gymnastics unless work ends early.'):
   with self.assertRaises(ValueError):HouseholdThinking.validate_goal(text,board)
 def test_natural_duration_phrases_are_computed_in_code(self):
  for value,want in [('Could we fit half an hour for dinner?',30),('a quarter of an hour',15),('about 45 minutes',45),('1.5 hours',90)]:self.assertEqual(duration_minutes(value),want)
  self.assertEqual(duration_quotes('About 45 minutes'),['45 minutes'])
if __name__=='__main__':unittest.main()
