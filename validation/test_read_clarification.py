import unittest
from types import SimpleNamespace
from datetime import datetime,timezone
from jarvis.read_clarification import resolve,pending,named,partial
from jarvis.companion_store import CompanionStore
from test_planning_preparation_bundle import profile
class ClarificationTests(unittest.TestCase):
 def setUp(self):self.clock=[1];self.owner=SimpleNamespace(profile=profile(),clock=lambda:self.clock[0],now=lambda:datetime(2026,11,2,12,tzinfo=timezone.utc));self.state={}
 def test_day_then_possessive_name_keeps_day(self):
  with self.assertRaisesRegex(ValueError,'Whose'):resolve(self.owner,'monday','plans',self.state,None)
  out=resolve(self.owner,'mias','plans',self.state,None);self.assertEqual(out['subjects'],['mia']);self.assertEqual(out['start'],'2026-11-02');self.assertNotIn('read_clarification',self.state)
 def test_name_then_day_keeps_person(self):
  with self.assertRaisesRegex(ValueError,'Which day'):resolve(self.owner,'mia','plans',self.state,None)
  out=resolve(self.owner,'monday','plans',self.state,None);self.assertEqual(out['subjects'],['mia']);self.assertEqual(out['end'],'2026-11-03')
 def test_date_reply_keeps_the_explicit_preparation_task(self):
  task='What should Mia prepare for band rehearsal?';self.state['read_clarification']={'subjects':['mia'],'start':None,'end':None,'purpose':'preparation','tool':'appointments','task':task,'expires':301}
  out=resolve(self.owner,'monday','appointments',self.state,None);self.assertEqual(out['task'],task);self.assertEqual(out['purpose'],'preparation');self.assertEqual(out['subjects'],['mia'])
 def test_expiry_and_other_question_drop_slots(self):
  with self.assertRaises(ValueError):resolve(self.owner,'monday','plans',self.state,None)
  self.clock[0]=302;self.assertIsNone(pending(self.owner,self.state))
  with self.assertRaisesRegex(ValueError,'Which day'):resolve(self.owner,'mia','plans',self.state,None)
  resolve(self.owner,'What are the plans tomorrow?','plans',self.state,None);self.assertNotIn('read_clarification',self.state)
 def test_possessives_are_names_not_voice_identity_or_other_names(self):
  for value in ('mias',"Mia's",'Mia’s','tilbake til mias øving'):self.assertEqual(named(value,{'mia':'Mia'}),{'mia'})
  self.assertEqual(named('Miasen',{'mia':'Mia'}),set());self.assertEqual(partial('save mias appointment',{'mia':'Mia'}),(False,False));self.assertEqual(partial('my',{'mia':'Mia'}),(False,False))

class ScopeTests(unittest.IsolatedAsyncioTestCase):
 def setUp(self):
  from test_companion_agent import AgentTests
  AgentTests.setUp(self)
 async def test_read_draft_cannot_cross_account_source_profile_or_permissions(self):
  from jarvis.calendar_context import calendar_scope
  def seed():
   state=self.a.agent.state('chat','phone')
   with self.assertRaises(ValueError):resolve(self.a,'monday','plans',state,None)
   self.assertIn('read_clarification',state)
  with calendar_scope({'actor':'one','read':True,'write':True}):seed();self.assertNotIn('read_clarification',self.a.agent.state('other','phone'));self.assertNotIn('read_clarification',self.a.agent.state('chat','tablet'))
  with calendar_scope({'actor':'two','read':True,'write':True}):self.assertNotIn('read_clarification',self.a.agent.state('chat','phone'));seed();self.profile._data['revision']+=1;self.assertNotIn('read_clarification',self.a.agent.state('chat','phone'));seed()
  with calendar_scope({'actor':'two','read':True,'write':False}):self.assertNotIn('read_clarification',self.a.agent.state('chat','phone'))
 async def test_overview_retains_checked_event_identity_for_later_topic_return(self):
  from test_household_thinking import ThinkingTests
  from test_planning_preparation_bundle import scope
  f=ThinkingTests();f.setUp()
  try:
   with scope(f.p,'benny','s'):out=await f.thinking.handle('What does Mia have tomorrow?','s',tool_selected=True)
   self.assertEqual(out['status'],'success');self.assertEqual(len(f.thinking.sessions['s']['source_focus']),1);self.assertEqual(f.thinking.sessions['s']['source_focus'][0][0],'Fellesøving Korps')
  finally:f.doCleanups()
 async def test_generic_plan_cannot_invent_an_earlier_activity_quote(self):
  from test_companion_read_context import ReadTests,frame
  f=ReadTests();f.setUp()
  try:
   f.prior(task="What are Mia's plans?",purpose='overview',event_focus=[]);f.provider.frames.append(frame(purpose='preparation',activity_quote='øving',prior_activity_quote='',event_relation='continue',preparation_goal='kit',event_scope='focused'));f.state['returned_topic']={'subjects':['mia']}
   await f.a.agent.reads.resolve('Tilbake til mias øving, hva må hun ta med?','appointments',['mia'],f.state)
   self.assertEqual(f.provider.calls[-1]['response_schema']['properties']['prior_activity_quote']['enum'],[''])
  finally:f.doCleanups()
 async def test_school_finish_does_not_focus_the_unrelated_calendar_rehearsal(self):
  from test_household_thinking import ThinkingTests
  from test_planning_preparation_bundle import scope
  f=ThinkingTests();f.setUp()
  try:
   with scope(f.p,'benny','s'):out=await f.thinking.handle('What time does Mia finish school tomorrow?','s',tool_selected=True)
   self.assertEqual(out['status'],'success');self.assertEqual(f.thinking.sessions['s']['source_focus'],[])
  finally:f.doCleanups()
